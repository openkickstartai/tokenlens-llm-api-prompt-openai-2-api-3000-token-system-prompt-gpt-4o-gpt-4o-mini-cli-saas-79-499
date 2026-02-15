# 🔍 TokenLens — LLM API Cost Attribution & Prompt Optimization Engine

Track every dollar of your LLM spend to the exact feature, endpoint, and user. Detect prompt bloat, suggest model downgrades, and enforce budgets before the bill shocks your CFO.

## 🚀 Quick Start

```bash
pip install -r requirements.txt
```

### Python SDK (2 lines to integrate)

```python
from tokenlens import TokenLens

lens = TokenLens(budget_usd=500)  # monthly budget circuit breaker

@lens.track("chat-feature", model="gpt-4o")
def ask_llm(prompt):
    response = openai.chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": prompt}]
    )
    return response

ask_llm("Summarize this document")
```

### CLI Reports

```bash
# Cost breakdown by feature
python cli.py report --by feature

# Cost breakdown by model
python cli.py report --by model

# Detect bloat + downgrade suggestions
python cli.py analyze

# Monthly summary
python cli.py summary
```

## 📊 Why Pay for TokenLens?

Teams using GPT-4o/Claude typically overspend **30-60%** due to:
- 🎈 **Prompt bloat**: system prompts inflated to 3000+ tokens with redundant instructions
- 🔨 **Model overkill**: using GPT-4o ($10/1M output) for simple classification that GPT-4o-mini ($0.60/1M) handles equally well
- 🔄 **Retry storms**: uncached repeated calls costing 5-10x what they should
- 🫣 **No visibility**: monthly bill arrives with zero attribution to features/teams

TokenLens pays for itself in the first week. A single model downgrade suggestion can save $500+/month.

## 💰 Pricing

| Feature | Free | Pro $79/mo | Enterprise $499/mo |
|---|---|---|---|
| Cost attribution (feature/model) | ✅ | ✅ | ✅ |
| CLI reports | ✅ | ✅ | ✅ |
| SQLite storage | ✅ | ✅ | ✅ |
| Prompt bloat detection | 100 calls/day | Unlimited | Unlimited |
| Model downgrade suggestions | Basic | Advanced + quality scoring | Advanced + A/B testing |
| Budget enforcement / circuit breaker | ❌ | ✅ | ✅ |
| PostgreSQL + multi-tenant | ❌ | ❌ | ✅ |
| Slack / PagerDuty alerts | ❌ | ✅ | ✅ |
| SSO + audit trail | ❌ | ❌ | ✅ |
| SaaS dashboard | ❌ | ✅ | ✅ |
| PDF cost reports | ❌ | ✅ | ✅ |
| Semantic cache detection | ❌ | ✅ | ✅ |
| GitHub Action integration | ❌ | ✅ | ✅ |
| Support | Community | Email | Dedicated Slack |

## 🏗️ Supported Models

GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-4, GPT-3.5-turbo, Claude 3.5 Sonnet, Claude 3 Haiku, Claude 3 Opus — with auto-updated pricing.

## 🧪 Run Tests

```bash
pytest test_tokenlens.py -v
```

## License

BSL 1.1 — Free for teams under $10k/mo LLM spend. Commercial license required above.
