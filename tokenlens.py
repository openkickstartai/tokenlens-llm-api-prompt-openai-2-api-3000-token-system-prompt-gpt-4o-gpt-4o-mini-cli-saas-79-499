"""TokenLens — LLM API Cost Attribution & Optimization SDK."""
import sqlite3
import time
import functools
from datetime import datetime

MODEL_PRICING = {  # USD per 1M tokens: (input, output)
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-opus": (15.00, 75.00),
}

MODEL_DOWNGRADES = {
    "gpt-4o": "gpt-4o-mini",
    "gpt-4-turbo": "gpt-4o",
    "gpt-4": "gpt-4o",
    "claude-3-5-sonnet": "claude-3-haiku",
    "claude-3-opus": "claude-3-5-sonnet",
}


class BudgetExceeded(Exception):
    """Raised when monthly budget is exceeded (circuit breaker)."""


class TokenLens:
    """Core tracker: records LLM calls, computes costs, detects waste."""

    def __init__(self, db_path="tokenlens.db", budget_usd=None):
        self.db_path = db_path
        self.budget_usd = budget_usd
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS calls ("
                "id INTEGER PRIMARY KEY, ts TEXT, feature TEXT, endpoint TEXT,"
                "user_id TEXT, model TEXT, input_tokens INT, output_tokens INT,"
                "cost_usd REAL, duration_ms REAL)"
            )

    def record(self, feature, model, input_tokens, output_tokens,
               endpoint="", user_id="", duration_ms=0.0):
        """Record a single LLM call. Returns cost in USD."""
        cost = self.calc_cost(model, input_tokens, output_tokens)
        if self.budget_usd is not None:
            projected = self.month_total() + cost
            if projected > self.budget_usd:
                raise BudgetExceeded(
                    f"Budget ${self.budget_usd:.2f} would be exceeded: ${projected:.4f}"
                )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO calls (ts,feature,endpoint,user_id,model,"
                "input_tokens,output_tokens,cost_usd,duration_ms) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (datetime.utcnow().isoformat(), feature, endpoint, user_id,
                 model, input_tokens, output_tokens, cost, duration_ms),
            )
        return cost

    @staticmethod
    def calc_cost(model, input_tokens, output_tokens):
        """Calculate cost in USD for a given model and token counts."""
        inp_price, out_price = MODEL_PRICING.get(model, (5.0, 15.0))
        return (input_tokens * inp_price + output_tokens * out_price) / 1_000_000

    def track(self, feature, model=None):
        """Decorator: auto-record cost of any function returning LLM response."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                mdl = model or kwargs.get("model", "gpt-4o")
                start = time.time()
                result = func(*args, **kwargs)
                dur = (time.time() - start) * 1000
                inp = out = 0
                if isinstance(result, dict) and "usage" in result:
                    inp = result["usage"].get("prompt_tokens", 0)
                    out = result["usage"].get("completion_tokens", 0)
                elif hasattr(result, "usage") and result.usage:
                    inp = getattr(result.usage, "prompt_tokens", 0)
                    out = getattr(result.usage, "completion_tokens", 0)
                self.record(feature, mdl, inp, out, duration_ms=dur)
                return result
            return wrapper
        return decorator

    def month_total(self):
        """Total cost USD for the current calendar month."""
        start = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd),0) FROM calls WHERE ts>=?", (start,)
            ).fetchone()
        return row[0]

    def cost_by(self, col):
        """Aggregate costs grouped by column (feature/model/user_id/endpoint)."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {col}, SUM(cost_usd), SUM(input_tokens+output_tokens),"
                f" COUNT(*) FROM calls GROUP BY {col} ORDER BY 2 DESC"
            ).fetchall()
        return [{"name": r[0] or "unknown", "cost_usd": r[1],
                 "tokens": r[2], "calls": r[3]} for r in rows]

    def detect_bloat(self, threshold=2000):
        """Find features with avg input tokens above threshold."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT feature,model,AVG(input_tokens),MAX(input_tokens),COUNT(*)"
                " FROM calls WHERE input_tokens>? GROUP BY feature,model",
                (threshold,),
            ).fetchall()
        return [{"feature": r[0], "model": r[1], "avg_input": r[2],
                 "max_input": r[3], "calls": r[4]} for r in rows]

    def suggest_downgrades(self):
        """Suggest cheaper models and compute projected savings."""
        results = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT model,SUM(cost_usd),SUM(input_tokens),"
                "SUM(output_tokens),COUNT(*) FROM calls GROUP BY model"
            ).fetchall()
        for model, cost, inp, out, count in rows:
            alt = MODEL_DOWNGRADES.get(model)
            if alt:
                alt_cost = self.calc_cost(alt, inp, out)
                if cost > alt_cost:
                    results.append({
                        "current_model": model, "suggested_model": alt,
                        "current_cost": cost, "projected_cost": alt_cost,
                        "monthly_saving": round(cost - alt_cost, 6), "calls": count,
                    })
        return results
