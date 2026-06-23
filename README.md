# token-saver

Drop-in Anthropic client wrapper with token counting, cost analysis, and semantic compression.

## Install

```bash
pip install -e .
```

## Quick Start

```python
from token_saver import TokenSaverClient

client = TokenSaverClient()  # reads ANTHROPIC_API_KEY from env
messages = [{"role": "user", "content": "Hello!"}]

# Count tokens before sending
tc = client.count_tokens(model="claude-sonnet-4-6", messages=messages)
print(tc.format())

# Estimate cost
est = client.estimate_cost(model="claude-sonnet-4-6", messages=messages, estimated_output_tokens=500)
print(est.format())

# Analyze for optimization opportunities
report = client.analyze(model="claude-sonnet-4-6", messages=messages)
print(report.format())

# Send request (usage tracked automatically)
response = client.create(model="claude-sonnet-4-6", max_tokens=1024, messages=messages)

# Compress long conversations
result = client.compress(model="claude-sonnet-4-6", messages=long_chat, target_reduction=0.5)
print(result.format())

# Monthly projection based on tracked usage
print(client.monthly_projection(requests_per_day=100).format())

# Full session summary
print(client.usage_summary())
```

## Features

- **Token counting** via the official `count_tokens` API (not tiktoken)
- **Cost estimation** with current pricing for all Claude models
- **Prescriptive analysis** — detects large messages, missing caching, long conversations, and suggests cheaper models
- **Semantic compression** — summarizes older conversation turns while preserving recent context and relevant messages
- **Usage tracking** — every `create()` call records tokens and cost
- **Monthly projection** — extrapolate costs from observed usage
