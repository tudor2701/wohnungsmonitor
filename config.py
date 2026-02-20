"""Zentrale Konfiguration – lädt alle Einstellungen aus der .env-Datei."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Zeitplan ---
CHECK_INTERVAL_MINUTES: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))

# --- Suchparameter ---
MIN_ROOMS: int = 4
CITY: str = "Aachen"

# Schlüsselwörter zur Stadtteil-Filterung (case-insensitive)
NEIGHBORHOOD_KEYWORDS: list[str] = ["frankenberger", "burtscheid"]

# Auf true setzen, um nur Inserate aus den Ziel-Stadtteilen zu melden
FILTER_BY_NEIGHBORHOOD: bool = os.getenv("FILTER_BY_NEIGHBORHOOD", "true").lower() == "true"

# Datei zum Speichern bereits gesehener Inserate
SEEN_LISTINGS_FILE: str = "seen_listings.json"


def validate_config() -> list[str]:
    """Prüft ob alle Pflichtfelder gesetzt sind. Gibt Liste mit Fehlermeldungen zurück."""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN ist nicht gesetzt")
    if not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID ist nicht gesetzt")
    return errors
