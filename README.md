# Wohnungsmonitor — Apartment Alert Bot

Get a push notification the moment a matching apartment goes online. Finding a flat in a popular neighbourhood is a speed game — good listings are gone within hours. This bot watches the three biggest German rental platforms every 15 minutes and sends new listings straight to Telegram, so I can reply before everyone else.

![Python](https://img.shields.io/badge/Python-3.10+-3776ab) ![Telegram](https://img.shields.io/badge/notifications-Telegram-26a5e4)

## How it works

```
every 15 min ─► ImmobilienScout24 ─┐
                Immowelt ──────────┼─► filter (rooms + neighbourhood) ─► dedupe ─► Telegram
                Kleinanzeigen ─────┘                                    (JSON)
```

1. **Scrape** each platform's search results for the target city and minimum room count.
2. **Parse** listings — preferring the embedded `__NEXT_DATA__` JSON where a site ships it, with an HTML fallback when it doesn't.
3. **Filter** to the target neighbourhoods by matching keywords in title, address and description (can be switched off for the whole city).
4. **Deduplicate** against a local JSON store, so every listing is sent exactly once.
5. **Notify** via the Telegram Bot API with title, address, rent, size, rooms and a direct link.

## Design notes

- **One interface, many sources.** Every platform is a `BaseScraper` subclass returning normalised `Listing` objects. Adding a new platform means writing one class.
- **Fails soft.** Blocks (HTTP 403), timeouts and parse errors are logged per platform; one broken source never stops the others.
- **Marked as seen only after delivery.** If a Telegram message fails, the listing is retried on the next run instead of being lost.
- **Polite by default.** Request delays and a configurable interval keep load on the platforms low.

## Getting started

```bash
git clone https://github.com/tudor2701/wohnungsmonitor.git
cd wohnungsmonitor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```dotenv
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHAT_ID=987654321
CHECK_INTERVAL_MINUTES=15
FILTER_BY_NEIGHBORHOOD=true
```

- **Bot token:** message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`.
- **Chat ID:** message [@userinfobot](https://t.me/userinfobot), or send your bot a message and read `chat.id` from `https://api.telegram.org/bot<TOKEN>/getUpdates`.

```bash
python main.py
```

On start, the bot sends a confirmation message, checks all platforms immediately, then repeats on schedule. Search city, room count and neighbourhood keywords are set in `config.py` and the search URLs in `scrapers/`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Required |
| `TELEGRAM_CHAT_ID` | — | Required |
| `CHECK_INTERVAL_MINUTES` | `15` | Polling interval |
| `FILTER_BY_NEIGHBORHOOD` | `true` | `false` = whole city |

## Run in the background (macOS)

Use a LaunchAgent with `RunAtLoad` and `KeepAlive` pointing to `.venv/bin/python main.py`, or simply:

```bash
nohup python main.py > /dev/null 2>&1 &
```

Logs are written to `wohnungsmonitor.log`.

## Project structure

```
main.py                     entry point + scheduler
config.py                   settings (loaded from .env)
storage.py                  JSON store of already-sent listings
scrapers/
  base.py                   Listing dataclass + BaseScraper
  immoscout.py              ImmobilienScout24
  immowelt.py               Immowelt
  kleinanzeigen.py          Kleinanzeigen
services/
  telegram_service.py       Telegram Bot API
```

## Limitations

- Platforms use anti-bot measures; ImmobilienScout24 in particular may block requests. A longer interval usually helps.
- Not every listing names its neighbourhood, so keyword filtering can miss some — disable it to see everything in the city.
- Built for personal use. Please respect each platform's terms of service.
