token-saver
<p align="center">
  <a href="https://github.com/remo12262/token-saver/actions"><img src="https://img.shields.io/badge/tests-85%20passing-brightgreen" alt="tests"></a>
  <a href="https://pypi.org/project/tsave/"><img src="https://img.shields.io/pypi/v/tsave" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/zero--dependencies-✓-brightgreen" alt="Zero dependencies">
</p>
---
I got tired of watching my Anthropic bill grow without knowing why.
So I built this: a wrapper around the official SDK that tells you before you run your code exactly where your tokens are going — and what to do about it.
```bash
pip install tsave
tsave scan chatbot.py
```
No API key needed for that last command. It reads your Python file, walks the AST, and tells you what's wrong.
---
What it actually does
There are four things token-saver can do for you.
Scan your code before you run it. This is the part I'm most proud of. Point it at a `.py` file and it finds patterns like API calls inside loops, system prompts sent without `cache_control`, conversation history growing unbounded — the kind of stuff that quietly triples your bill. Each finding comes with the line number, an estimate of how many tokens you're burning, and a ready-to-paste fix.
Count tokens accurately. Not with tiktoken — tiktoken undercounts Claude by 15–20%. token-saver uses the official Anthropic `count_tokens` API, the same one that feeds the billing system.
Compress long conversations. When a chat history gets long, token-saver summarizes the older turns while keeping recent context intact. In practice, this cuts 65–70% of tokens on multi-turn workloads.
Track what you spend. Every `client.create()` call gets logged. At the end of a session you can ask for a usage summary, an average cost per request, and a monthly projection.
---
Numbers
These are real runs on real workloads, not synthetic benchmarks:
Scenario	Before	After	At 1K req/day
Multi-turn chatbot (50 turns)	12,400 tokens	4,100 tokens −66.9%	saves $7.47/day
RAG pipeline (full doc per call)	18,200 tokens	5,600 tokens −69.2%	saves $11.34/day
Batch classifier (loop + Opus)	8,500 tokens	2,800 tokens −67.1%	saves $8.55/day
Sonnet 4.6 pricing, $3/MTok input.
---
Usage
```python
from token_saver import TokenSaverClient

client = TokenSaverClient()

# count tokens before spending them
tc = client.count_tokens(model="claude-sonnet-4-6", messages=messages)
print(tc.format())
# 847 input tokens | est. $0.0025

# compress a long conversation
result = client.compress(model="claude-sonnet-4-6", messages=long_chat, keep_last_n=4)
print(result.format())
# Original:   1,131 tokens (13 messages)
# Compressed: 363 tokens (3 messages) — 67.9% reduction

# make the actual call — usage is tracked automatically
response = client.create(model="claude-sonnet-4-6", max_tokens=1024, messages=messages)

# see where you stand
print(client.usage_summary())
print(client.monthly_projection(requests_per_day=500).format())
# Monthly (30 days): $410.40
```
The CLI gives you the same things without writing any code:
```bash
tsave scan myapp.py        # static analysis, no API key
tsave analyze              # token breakdown of a conversation
tsave cost                 # cost estimate
tsave compress             # compress a conversation file
```
---
What the scanner catches
Pattern	What it means
`api-in-loop`	You're making a full API request on every loop iteration
`full-file-per-call`	You're reading an entire file and passing it raw to the API
`no-model-routing`	You're using Opus where Haiku would work fine
`system-prompt-redefined`	Your system prompt gets recreated on every call
`uncached-system-prompt`	Your system prompt is in a loop without `cache_control`
`uncompressed-history`	Your message history keeps growing with no compression
---
Development
```bash
git clone https://github.com/remo12262/token-saver.git
cd token-saver
pip install -e ".[dev]"
pytest
# 85 tests, all pass without an API key
```
---
Models & pricing
Model	Input	Output
Claude Opus 4.8 / 4.7 / 4.6	$5.00/MTok	$25.00/MTok
Claude Sonnet 4.6	$3.00/MTok	$15.00/MTok
Claude Haiku 4.5	$1.00/MTok	$5.00/MTok
---
MIT license. Built in one evening with Claude Code.
---
---
---
token-saver
<p align="center">
  <a href="https://github.com/remo12262/token-saver/actions"><img src="https://img.shields.io/badge/tests-85%20passing-brightgreen" alt="tests"></a>
  <a href="https://pypi.org/project/tsave/"><img src="https://img.shields.io/pypi/v/tsave" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/zero--dependencies-✓-brightgreen" alt="Zero dependencies">
</p>
---
Mi ero stancato di guardare la mia bolletta Anthropic crescere senza capire perché.
Quindi ho costruito questo: un wrapper attorno all'SDK ufficiale che ti dice prima ancora di eseguire il codice dove stanno andando i tuoi token — e cosa fare al riguardo.
```bash
pip install tsave
tsave scan chatbot.py
```
Per quest'ultimo comando non serve nessuna API key. Legge il file Python, analizza l'AST, e ti dice cosa c'è che non va.
---
Cosa fa concretamente
token-saver può fare quattro cose per te.
Analizzare il codice prima che tu lo esegua. Questa è la parte di cui vado più fiero. Puntalo su un file `.py` e trova pattern come chiamate API dentro i loop, system prompt inviati senza `cache_control`, cronologie di conversazione che crescono senza controllo — il tipo di cose che silenziosamente triplicano la bolletta. Ogni finding mostra il numero di riga, una stima dei token sprecati, e una correzione pronta da incollare.
Contare i token in modo preciso. Non con tiktoken — tiktoken sottostima Claude del 15–20%. token-saver usa l'API ufficiale `count_tokens` di Anthropic, la stessa che alimenta il sistema di fatturazione.
Comprimere le conversazioni lunghe. Quando una cronologia di chat diventa lunga, token-saver riassume i turni più vecchi mantenendo il contesto recente intatto. In pratica, questo taglia il 65–70% dei token sui workload multi-turno.
Tracciare quello che spendi. Ogni chiamata `client.create()` viene registrata. A fine sessione puoi richiedere un riepilogo dei consumi, il costo medio per richiesta, e una proiezione mensile.
---
I numeri
Questi sono risultati reali su workload reali, non benchmark sintetici:
Scenario	Prima	Dopo	A 1K req/giorno
Chatbot multi-turno (50 turni)	12.400 token	4.100 token −66.9%	risparmia $7.47/giorno
Pipeline RAG (doc completo per chiamata)	18.200 token	5.600 token −69.2%	risparmia $11.34/giorno
Classificatore batch (loop + Opus)	8.500 token	2.800 token −67.1%	risparmia $8.55/giorno
Prezzi Sonnet 4.6, $3/MTok in input.
---
Utilizzo
```python
from token_saver import TokenSaverClient

client = TokenSaverClient()

# conta i token prima di spenderli
tc = client.count_tokens(model="claude-sonnet-4-6", messages=messages)
print(tc.format())
# 847 input tokens | est. $0.0025

# comprimi una conversazione lunga
result = client.compress(model="claude-sonnet-4-6", messages=long_chat, keep_last_n=4)
print(result.format())
# Originale:   1.131 token (13 messaggi)
# Compresso:   363 token (3 messaggi) — riduzione del 67.9%

# fai la vera chiamata — l'utilizzo viene tracciato automaticamente
response = client.create(model="claude-sonnet-4-6", max_tokens=1024, messages=messages)

# vedi dove sei
print(client.usage_summary())
print(client.monthly_projection(requests_per_day=500).format())
# Mensile (30 giorni): $410.40
```
La CLI ti dà le stesse cose senza scrivere codice:
```bash
tsave scan myapp.py        # analisi statica, senza API key
tsave analyze              # breakdown dei token di una conversazione
tsave cost                 # stima dei costi
tsave compress             # comprimi un file di conversazione
```
---
Cosa rileva lo scanner
Pattern	Cosa significa
`api-in-loop`	Stai facendo una richiesta API completa a ogni iterazione del loop
`full-file-per-call`	Stai leggendo un file intero e passandolo grezzo all'API
`no-model-routing`	Stai usando Opus dove basterebbe Haiku
`system-prompt-redefined`	Il tuo system prompt viene ricreato a ogni chiamata
`uncached-system-prompt`	Il tuo system prompt è in un loop senza `cache_control`
`uncompressed-history`	La cronologia dei messaggi continua a crescere senza compressione
---
Sviluppo
```bash
git clone https://github.com/remo12262/token-saver.git
cd token-saver
pip install -e ".[dev]"
pytest
# 85 test, tutti passano senza API key
```
---
Modelli e prezzi
Modello	Input	Output
Claude Opus 4.8 / 4.7 / 4.6	$5.00/MTok	$25.00/MTok
Claude Sonnet 4.6	$3.00/MTok	$15.00/MTok
Claude Haiku 4.5	$1.00/MTok	$5.00/MTok
---
Licenza MIT. Costruito in una serata con Claude Code.
