"""Tests for TokenLens core SDK."""
import os
import pytest
from tokenlens import TokenLens, BudgetExceeded, MODEL_PRICING, MODEL_DOWNGRADES

DB = "test_tokenlens.db"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    if os.path.exists(DB):
        os.remove(DB)


def test_record_and_cost_calculation():
    """Verify cost math: gpt-4o 1000in/500out = $0.0075."""
    lens = TokenLens(db_path=DB)
    cost = lens.record("chat", "gpt-4o", 1000, 500)
    expected = (1000 * 2.50 + 500 * 10.00) / 1_000_000  # 0.0075
    assert cost == pytest.approx(expected, rel=1e-6)


def test_cost_attribution_by_feature():
    """Two features tracked, most expensive should rank first."""
    lens = TokenLens(db_path=DB)
    lens.record("chat", "gpt-4o", 1000, 500)
    lens.record("search", "gpt-4o-mini", 500, 200)
    by_feat = lens.cost_by("feature")
    assert len(by_feat) == 2
    assert by_feat[0]["name"] == "chat"  # gpt-4o is more expensive
    assert by_feat[0]["cost_usd"] > by_feat[1]["cost_usd"]


def test_cost_attribution_by_model():
    """Group by model returns correct aggregates."""
    lens = TokenLens(db_path=DB)
    lens.record("a", "gpt-4o", 1000, 200)
    lens.record("b", "gpt-4o", 2000, 300)
    lens.record("c", "gpt-4o-mini", 500, 100)
    by_model = lens.cost_by("model")
    assert len(by_model) == 2
    gpt4o = [m for m in by_model if m["name"] == "gpt-4o"][0]
    assert gpt4o["calls"] == 2


def test_budget_enforcement_blocks_call():
    """Circuit breaker raises BudgetExceeded when spend exceeds limit."""
    lens = TokenLens(db_path=DB, budget_usd=0.001)
    lens.record("chat", "gpt-4o", 100, 50)
    with pytest.raises(BudgetExceeded, match="exceeded"):
        lens.record("chat", "gpt-4o", 1_000_000, 500_000)


def test_budget_allows_within_limit():
    """Calls within budget should succeed without error."""
    lens = TokenLens(db_path=DB, budget_usd=100.0)
    cost = lens.record("chat", "gpt-4o", 1000, 500)
    assert cost > 0
    assert lens.month_total() == pytest.approx(cost)


def test_detect_bloat_finds_large_prompts():
    """Prompts above threshold should be flagged as bloat."""
    lens = TokenLens(db_path=DB)
    for _ in range(3):
        lens.record("email-gen", "gpt-4o", 3500, 200)
    lens.record("classify", "gpt-4o-mini", 100, 20)
    bloat = lens.detect_bloat(threshold=2000)
    assert len(bloat) == 1
    assert bloat[0]["feature"] == "email-gen"
    assert bloat[0]["avg_input"] == pytest.approx(3500)


def test_detect_bloat_empty_when_clean():
    """No bloat should be detected for small prompts."""
    lens = TokenLens(db_path=DB)
    lens.record("classify", "gpt-4o-mini", 100, 20)
    assert lens.detect_bloat(threshold=2000) == []


def test_suggest_downgrades():
    """gpt-4o usage should suggest gpt-4o-mini with positive savings."""
    lens = TokenLens(db_path=DB)
    lens.record("chat", "gpt-4o", 5000, 1000)
    lens.record("chat", "gpt-4o", 5000, 1000)
    suggestions = lens.suggest_downgrades()
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s["current_model"] == "gpt-4o"
    assert s["suggested_model"] == "gpt-4o-mini"
    assert s["monthly_saving"] > 0
    assert s["projected_cost"] < s["current_cost"]


def test_no_downgrade_for_cheapest_model():
    """gpt-4o-mini has no cheaper alternative — no suggestion."""
    lens = TokenLens(db_path=DB)
    lens.record("classify", "gpt-4o-mini", 500, 100)
    assert lens.suggest_downgrades() == []


def test_decorator_tracking():
    """@track decorator should auto-extract usage from dict result."""
    lens = TokenLens(db_path=DB)

    @lens.track("summarize", model="gpt-4o")
    def fake_llm():
        return {"usage": {"prompt_tokens": 800, "completion_tokens": 200}}

    result = fake_llm()
    assert result["usage"]["prompt_tokens"] == 800
    by_feat = lens.cost_by("feature")
    assert len(by_feat) == 1
    assert by_feat[0]["name"] == "summarize"
    expected_cost = TokenLens.calc_cost("gpt-4o", 800, 200)
    assert by_feat[0]["cost_usd"] == pytest.approx(expected_cost)


def test_model_pricing_completeness():
    """All models in downgrade map must have pricing entries."""
    for model in MODEL_DOWNGRADES:
        assert model in MODEL_PRICING, f"{model} missing pricing"
        alt = MODEL_DOWNGRADES[model]
        assert alt in MODEL_PRICING, f"{alt} missing pricing"
        orig_in, orig_out = MODEL_PRICING[model]
        alt_in, alt_out = MODEL_PRICING[alt]
        assert alt_in <= orig_in, f"{alt} input not cheaper than {model}"
