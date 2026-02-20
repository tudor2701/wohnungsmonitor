# Wohnungs-Monitor 🏠

Überwacht **ImmobilienScout24**, **Immowelt** und **Kleinanzeigen** automatisch auf neue 4-Zimmer-Mietwohnungen in Aachen (Frankenberger Viertel & Burtscheid) und sendet dir per Telegram eine Benachrichtigung mit Link und einer von Claude generierten Kontaktnachricht.

---

## Projektstruktur

```
Wohnung/
├── main.py                    # Einstiegspunkt
├── config.py                  # Konfiguration (lädt .env)
├── storage.py                 # Speichert bereits gesehene Inserate
├── scrapers/
│   ├── base.py                # Basisklassen (Listing, BaseScraper)
│   ├── immoscout.py           # ImmobilienScout24-Scraper
│   ├── immowelt.py            # Immowelt-Scraper
│   └── kleinanzeigen.py       # Kleinanzeigen-Scraper
├── services/
│   ├── claude_service.py      # Anthropic Claude API (Nachrichtengenerierung)
│   └── telegram_service.py    # Telegram Bot API (Benachrichtigungen)
├── requirements.txt
├── .env.example               # Vorlage für Umgebungsvariablen
└── seen_listings.json         # Wird automatisch erstellt
```

---

## Schritt-für-Schritt Einrichtung

### 1. Python-Version prüfen

```bash
python3 --version
# Mindestens Python 3.10 erforderlich
```

### 2. Virtuelle Umgebung erstellen & Dependencies installieren

```bash
cd Wohnung
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# oder: .venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 3. API-Keys & Tokens besorgen

#### Telegram Bot erstellen

1. Öffne Telegram und suche nach **@BotFather**
2. Sende `/newbot` und folge den Anweisungen
3. Am Ende erhältst du einen **Bot-Token** (Format: `123456789:ABCdef...`)

#### Deine Telegram Chat-ID herausfinden

1. Suche nach **@userinfobot** auf Telegram
2. Schreibe ihm `/start` – er antwortet mit deiner **Chat-ID**
3. Alternativ: Schreibe deinem Bot eine Nachricht, dann rufe auf:
   ```
   https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates
   ```
   In der Antwort steht `"id"` unter `"chat"`.

#### Anthropic API-Key holen

1. Gehe zu [console.anthropic.com](https://console.anthropic.com)
2. Erstelle einen Account (falls noch nicht vorhanden)
3. Unter **API Keys** → **Create Key**

### 4. `.env`-Datei anlegen

```bash
cp .env.example .env
```

Öffne `.env` und trage deine Werte ein:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=987654321
ANTHROPIC_API_KEY=sk-ant-...
CHECK_INTERVAL_MINUTES=15
FILTER_BY_NEIGHBORHOOD=true
CLAUDE_MODEL=claude-haiku-4-5-20251001
```

### 5. Script starten

```bash
python main.py
```

Beim ersten Start:
- Wird eine Telegram-Bestätigungsnachricht gesendet
- Werden sofort alle Plattformen geprüft
- Läuft dann alle 15 Minuten automatisch weiter

---

## Dauerhaft im Hintergrund laufen lassen (macOS)

### Option A: `nohup` (einfach)

```bash
nohup python main.py > /dev/null 2>&1 &
echo $! > wohnungsmonitor.pid   # PID speichern

# Stoppen:
kill $(cat wohnungsmonitor.pid)
```

### Option B: launchd (empfohlen für macOS)

Erstelle `~/Library/LaunchAgents/com.wohnungsmonitor.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wohnungsmonitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/ABSOLUTER/PFAD/ZU/Wohnung/.venv/bin/python</string>
        <string>/ABSOLUTER/PFAD/ZU/Wohnung/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/ABSOLUTER/PFAD/ZU/Wohnung</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/ABSOLUTER/PFAD/ZU/Wohnung/wohnungsmonitor.log</string>
    <key>StandardErrorPath</key>
    <string>/ABSOLUTER/PFAD/ZU/Wohnung/wohnungsmonitor.log</string>
</dict>
</plist>
```

```bash
# Pfade anpassen, dann:
launchctl load ~/Library/LaunchAgents/com.wohnungsmonitor.plist

# Stoppen:
launchctl unload ~/Library/LaunchAgents/com.wohnungsmonitor.plist
```

---

## Konfigurationsoptionen

| Variable | Standard | Beschreibung |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | – | Pflicht: Bot-Token von @BotFather |
| `TELEGRAM_CHAT_ID` | – | Pflicht: Deine Telegram-Nutzer-ID |
| `ANTHROPIC_API_KEY` | – | Pflicht: API-Key für Claude |
| `CHECK_INTERVAL_MINUTES` | `15` | Prüfintervall in Minuten |
| `FILTER_BY_NEIGHBORHOOD` | `true` | `true` = nur Frankenberger/Burtscheid, `false` = ganz Aachen |
| `CLAUDE_MODEL` | `claude-haiku-4-5-20251001` | Claude-Modell (Haiku = günstig, Sonnet = besser) |

---

## Hinweise & bekannte Einschränkungen

### Anti-Bot-Maßnahmen
Alle drei Plattformen können Scraping erkennen und blockieren:
- **ImmobilienScout24** ist am aggressivsten mit Schutzmaßnahmen (CAPTCHA, IP-Blocks)
- **Immowelt** und **Kleinanzeigen** sind in der Regel zugänglicher

Wenn eine Plattform keine Ergebnisse liefert, schau ins Log (`wohnungsmonitor.log`). Bei dauerhaftem `403`-Fehler hilft oft:
1. Längeres Prüfintervall (`CHECK_INTERVAL_MINUTES=30`)
2. Warten (manche Blocks lösen sich nach einigen Stunden)

### Stadtteil-Filterung
Da nicht alle Inserate explizit den Stadtteil nennen, kannst du `FILTER_BY_NEIGHBORHOOD=false` setzen, um alle 4-Zimmer-Wohnungen in Aachen zu sehen. Der Filter sucht nach den Schlüsselwörtern `frankenberger` und `burtscheid` im Titel, der Adresse und der Beschreibung.

### Log-Datei
Das Script schreibt Logs nach `wohnungsmonitor.log`. Dort siehst du:
- Wie viele Inserate pro Plattform gefunden wurden
- Welche neu sind und gemeldet wurden
- Eventuelle Fehler (API-Blocks, Verbindungsprobleme)

---

## Telegram-Nachrichtenformat

```
🏡 Neue Wohnung auf ImmobilienScout24!

Schöne 4-Zimmer-Wohnung in Aachen-Burtscheid

📍 Burtscheider Markt 5, 52066 Aachen
💶 1.200 € Kaltmiete
📐 98 m²
🚪 4 Zimmer

🔗 Zum Inserat

──────────────────────────────

📝 Vorgeschlagene Kontaktnachricht:

Guten Tag,

ich bin auf Ihre Anzeige für die 4-Zimmer-Wohnung am Burtscheider
Markt aufmerksam geworden und würde mich sehr über eine Besichtigung
freuen. [...]
```
