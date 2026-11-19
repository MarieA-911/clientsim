# clientsim

**Test your AI chatbot against hundreds of simulated customers — before your real ones do.**

[Français](README.fr.md) · MIT licence · made by [JustiLoi](https://www.justiloi.com)

You wrote a system prompt, you tried your WhatsApp / website / Messenger assistant a few times, it looked fine,
you went live. Then a real customer wrote and... nothing came back. Or the bot invented a price. Or it promised
a callback and nobody was told.

`clientsim` invents realistic customers (in a hurry, suspicious, chatty, writing with typos or in another
language, haggling, asking for a human, replying STOP), has each of them talk to your bot, then a judge scores every
conversation against **your** rules and tells you exactly what to fix.

```
$ clientsim run -n 50 --budget 5        # example output
#0     8/10  $  0.05  asks about prices and what is included
#1     2/10  $  0.09  wants to book right now  ⚠ empty reply (stop_reason: max_tokens)
#2     6/10  $  0.14  negotiates or asks for a discount
...
Average 6.9/10 · 3 silent/broken · $3.12 spent
Report: runs/2026-11-19_1520/report.html
```

## The story behind it

We run a WhatsApp assistant for our own small company in Guadeloupe. On launch day, the first real prospect
coming from a paid ad wrote *"Hello, I want to try the assistant"* — and got **no answer**. No error anywhere.

We built `clientsim` that afternoon. On the first 5 simulated customers, the bot stayed silent **3 times**.
The cause: the model's *thinking* counts towards `max_tokens`; with a limit of 400 it sometimes used everything up
before writing a single word. Fixed in one line. Then 120 simulated conversations showed the next problems:
announcing *"the owner will call you back"* without actually alerting anyone, asking three questions at once,
answering in French to people writing in Creole.

Same 8 customers, same bot, before and after the one-line fix:

| Setting | Average score | Customers left without an answer |
|---|---|---|
| `max_tokens: 400` | **3.0 / 10** | **4 out of 8** |
| `max_tokens: 4000`, `effort: low` | **7.6 / 10** | 0 |

## Quick start

```bash
pip install git+https://github.com/MarieA-911/clientsim
export ANTHROPIC_API_KEY=sk-ant-...
clientsim init          # writes clientsim.yaml and bot_prompt.md
# describe your business in clientsim.yaml, paste your bot's instructions in bot_prompt.md
clientsim run -n 30 --budget 3
```

Open `runs/<date>/report.html`: average score, score distribution, most frequent issues, the rules the judge
suggests adding to your bot, and the worst conversations in full with a better reply for each.

Try the examples first: [`examples/pizzeria-en`](examples/pizzeria-en) and
[`examples/bakery-fr`](examples/bakery-fr) (a Guadeloupe bakery, with customers writing in Creole).

## Plug in your bot

Three ways, in `clientsim.yaml`:

```yaml
target:
  kind: anthropic                  # your bot is a Claude system prompt
  model: claude-sonnet-5-5
  system_prompt_file: bot_prompt.md
  max_tokens: 4000
  handoff_marker: "[HANDOFF]"      # optional: what your bot writes when a human must take over
```

```yaml
target:
  kind: http                       # your bot is already running somewhere
  url: https://example.com/bot     # POST {"messages": [{"role", "content"}...]} -> {"reply": "...", "handoff": false}
  headers: {Authorization: "Bearer ..."}
```

```yaml
target:
  kind: python                     # your bot is a Python function
  function: mybot.chat:reply       # reply(messages) -> str  or  {"reply": ..., "handoff": ...}
```

The bot can use any model or provider behind `http` or `python`; the simulated customers and the judge use Claude.

## Commands

| Command | What it does |
|---|---|
| `clientsim run` | invent customers, run the conversations, judge them, write the report |
| `clientsim run -o runs/x` | resume an interrupted run (finished conversations are never redone) |
| `clientsim replay runs/x --worst 10` | after fixing your bot, replay the 10 worst customers and compare scores |
| `clientsim rejudge runs/x` | score existing conversations again (after editing the rules) |
| `clientsim report runs/x` | rebuild the report |

## What it checks

Mechanically, without any AI judgement: empty replies, bot errors, replies cut by `max_tokens`, replies longer than
`max_words`. A silent reply caps the score at 2/10: a customer who gets nothing is a lost customer.

With a judge (Claude Opus 5.5) reading your rules: invented information, promises the business can't keep, wrong
offer, too long, several questions at once, unnecessary questions, missed or useless handoff to a human, tone,
ignored questions, wrong language, asking for passwords or card numbers, STOP not respected.

Handoff markers are hidden from the simulated customer but shown to the judge, so a correct handoff is never
counted as a missed one (a bug we hit ourselves).

## Cost

Every run has a hard budget (`budget_usd` or `--budget`). As a rough guide, a conversation costs 3 to 10 cents
with Claude Opus 5.5 as simulator and judge. 50 conversations: about $3.

## Good practice

- Describe the business precisely: prices, hours, what is *not* offered. Vague descriptions make vague customers.
- Write the persona mix you actually get (`persona_mix`, `personas_extra`): languages, tourists, elderly customers…
- Fix one thing, then `replay --worst 10` to check it helped before running a full batch again.
- Read the worst conversations yourself. The judge is good, not infallible.

## Made by JustiLoi

`clientsim` is built and maintained by [JustiLoi](https://www.justiloi.com), a small company from Guadeloupe that
sets up AI WhatsApp assistants for shops, craftsmen and independent professionals in the French overseas territories
and mainland France — tested with this tool before they talk to a single real customer.
Want one for your business? → [justiloi.com/assistant-whatsapp](https://www.justiloi.com/assistant-whatsapp)

Issues and pull requests welcome.
