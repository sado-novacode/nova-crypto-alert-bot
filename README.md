<div align="center">

# ⚡ Nova — Crypto Alert Bot

**A Telegram bot that understands plain language.** Write *"btc above 100k"* or
*«بیت‌کوین بالای ۱۰۰ هزار دلار»* — Nova parses it, watches Binance's live feed
and pings you the moment it happens.

`aiogram 3` · `Python 3.12` · `Binance WebSocket` · `SQLite (aiosqlite)` · `FA/EN`

</div>

## ✨ What makes Nova different

| | Feature | How it works |
|---|---|---|
| 🧠 | **Natural-language alerts** | Zero-form UX: `eth below 1800`, «سولانا اگر زیر ۹۰ رفت خبرم کن», `btc above 100k` — a multilingual regex-NLP parser (Persian digits `۱۲۳`, units `هزار/میلیون/k/m/b`, Persian coin names) turns sentences into structured rules. **Works fully offline — no external NLP API.** |
| 📡 | **Sub-second live feed** | Binance `!miniTicker@arr` WebSocket with auto-reconnect + exponential backoff; automatic REST fallback polling if the socket dies. 200+ symbols cached in memory. |
| 🚨 | **10 alert types, all one-shot** | Price above/below · ±% in 1h · ±% in 24h · **rapid drop/pump** (x% within N minutes) · **volume spike** (> N× 30-min baseline, illiquid-pair guard) · **trailing** (x% off rolling high, persisted across restarts) |
| 💼 | **Portfolio P&L** | `buy 0.5 eth at 2200` or «خرید ۰٫۵ اتریوم به قیمت ۲۲۰۰» — live value, total P&L, per-holding percentages. |
| ⭐ | **Watchlist** | `watch sol` — compact live list with 24h change, one-tap remove. |
| 🌅 | **Morning digest** | Opt-in daily summary: watchlist performance, portfolio P&L, top & bottom 24h movers. |
| 💎 | **Built-in monetization** | Free tier (5 alerts) + premium codes. Admin generates codes with `/gencode 10 30`, user redeems by pasting `NOVA-XXXX`. USDT wallet shown in `/premium` — the bot is a **product**, not just a demo. |
| 🌍 | **Bilingual FA/EN** | Every message, button and error in both languages; per-user choice; RTL-safe. |

## 🧾 Example conversation

```text
User:  بیت‌کوین بالای ۱۰۰ هزار دلار خبرم کن
Nova:  🧠 این‌طوری فهمیدم:
       BTC ⬆️ بالاتر رفت از $100,000
       💵 Now: $76,015
       [✅ Create/ثبت] [✖ Cancel/انصراف]

Nova:  ✅ هشدار ساخته شد — دارم می‌پرسم. به محض فعال شدن خبرت می‌کنم.
...
Nova:  🚨 هشدار نوا
       BTC الان $100,412 است
       📊 ۲۴س: ▲ 1.42%   📈 سقف ۲۴س: $100,510
       🎯 دلیل: price crossed above 100,000
```

## 🚀 Run it

> Needs **Python 3.11+**. No API keys besides a Telegram bot token.

```bash
# 1) clone & enter
cd nova-bot

# 2) create your bot with @BotFather -> /newbot -> copy the token
cp .env.example .env       # then paste your BOT_TOKEN (edit ADMIN_IDS too)

# 3) install & run
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

That's it — open Telegram and say *hi* to your bot. 🎉

<details>
<summary><b>Docker</b></summary>

```bash
docker build -t nova-bot .
docker run -d --env-file .env --name nova nova-bot
```
</details>

<details>
<summary><b>systemd (Linux VPS)</b></summary>

```bash
sudo cp systemd/nova-bot.service /etc/systemd/system/
# edit User= and WorkingDirectory= inside, then:
sudo systemctl daemon-reload
sudo systemctl enable --now nova-bot
journalctl -u nova-bot -f        # watch logs
```
</details>

## 🗂 Project structure

```
nova-bot/
├── run.py                  # entry point: wires db + market + engine + bot
├── nova/
│   ├── config.py           # env config, free-tier limits, guardrails
│   ├── models.py           # Ticker, AlertDraft + 10 alert types
│   ├── db.py               # async SQLite layer (users/alerts/holdings/codes)
│   ├── market.py           # Binance WS + REST fallback + ring buffers
│   ├── parser.py           # ⭐ multilingual NL parser (FA/EN)
│   ├── rules.py            # pure rule-evaluation functions (unit-tested)
│   ├── engine.py           # 10-second evaluation loop, one-shot firing
│   ├── digest.py           # daily morning digest scheduler
│   └── bot/
│       ├── handlers.py     # commands, guided flows, free-text router
│       ├── keyboards.py    # inline keyboards
│       ├── flows.py        # per-user guided-flow state machine
│       └── texts.py        # FA/EN strings + message builders
├── tests/
│   ├── test_parser.py      # 22 parser cases (FA + EN + negatives)
│   ├── test_rules.py       # pure rule checks
│   └── smoke_market.py     # live Binance connectivity check
├── Dockerfile
└── systemd/nova-bot.service
```

## 🧠 Design decisions worth mentioning in an interview

1. **Offline NLP over LLM calls** — the parser is pure regex + normalization tables. It's free, instant, deterministic and never leaks data; an LLM would add cost, latency and a failure mode for a task that structured patterns solve. (The parser is deliberately isolated — swapping it for an LLM extractor is a one-file change.)
2. **One-shot alerts with DB state** — every rule fires exactly once (`ACTIVE → TRIGGERED`), so restarts and multiple devices can't double-notify. Trailing highs are persisted into the alert's params to survive restarts.
3. **WS-first, REST-fallback market layer** — the feed auto-reconnects with backoff; if the socket is stale >30 s a chunked REST poller takes over, so one delisted symbol can never break the whole batch (learned that the hard way — `MATICUSDT`).
4. **Monetization as a first-class citizen** — tiers, limits and redeem codes live in the schema from day one; `redeem_code` is a single atomic SQL transaction (mark used + extend expiry).
5. **Pure-function rules** — every alert condition is a testable function `(snapshot → bool)` with zero IO; the engine only orchestrates.

## 🧪 Tests

```bash
python -m tests.test_parser     # NL parser: FA/EN/Persian-digits/negatives
python -m tests.test_rules      # rule engine: pure functions
python tests/smoke_market.py    # live Binance WS + REST check
```

## 🗺 Roadmap

- [ ] LLM fallback for sentences the regex parser can't understand
- [ ] On-chain whale alerts (large transfers)
- [ ] Inline-mode coin search (type `@yourbot btc` in any chat)
- [ ] Postgres backend swap for 10k+ users

## 📄 License

[MIT](LICENSE) © 2026 Nova

---

*Data: Binance public API. Not financial advice.*
