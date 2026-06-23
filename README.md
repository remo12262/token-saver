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

## Static Analyzer (CLI)

Scan Python source files for token-wasting patterns before execution:

```bash
tsave scan myapp.py
```

Example output:

```
tsave: myapp.py -- 3 issue(s)

  myapp.py:12  [api-in-loop]
  API call inside a loop -- each iteration sends a full request
  ~5,000 tokens wasted per call
  Fix:
    # Batch messages or collect results, then make one call
    results = []
    for item in items:
        results.append(item)
    response = client.messages.create(
        model="claude-haiku-4-5",
        messages=[{"role": "user", "content": "\n".join(results)}],
    )

  myapp.py:12  [no-model-routing]
  Using claude-opus-4-8 for a simple call -- Haiku may suffice
  ~0 tokens wasted per call
  Fix:
    # Route by complexity
    model = "claude-haiku-4-5"  # simple tasks
    # model = "claude-opus-4-8"     # complex tasks only

  myapp.py:8  [system-prompt-redefined]
  System prompt assigned 3 times -- define once and cache
  ~2,000 tokens wasted per call
  Fix:
    # Define once at module level with cache_control
    SYSTEM = [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]

Total estimated waste: ~7,000 tokens/call
```

### Rules detected

| Rule | Description |
|---|---|
| `api-in-loop` | API call inside for/while loop |
| `full-file-per-call` | `open().read()` passed directly in API call |
| `no-model-routing` | Expensive model used for simple calls |
| `system-prompt-redefined` | System prompt assigned multiple times |
| `uncached-system-prompt` | System prompt in loop without `cache_control` |
| `uncompressed-history` | Messages appended in loop without compression |

## Features

- **Token counting** via the official `count_tokens` API (not tiktoken)
- **Cost estimation** with current pricing for all Claude models
- **Prescriptive analysis** — detects large messages, missing caching, long conversations, and suggests cheaper models
- **Semantic compression** — summarizes older conversation turns while preserving recent context and relevant messages
- **Usage tracking** — every `create()` call records tokens and cost
- **Monthly projection** — extrapolate costs from observed usage
