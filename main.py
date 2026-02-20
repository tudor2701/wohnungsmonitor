#!/usr/bin/env python3
"""
Wohnungs-Monitor
================
Überwacht ImmobilienScout24, Immowelt und Kleinanzeigen auf neue
4-Zimmer-Mietwohnungen in Aachen (Frankenberger Viertel & Burtscheid)
und sendet Telegram-Benachrichtigungen mit Link und Inseratdetails.

Starten: python main.py
"""

import logging
import sys
import time

import schedule

import config
from scrapers.immoscout import ImmoScoutScraper
from scrapers.immowelt import ImmoweltScraper
from scrapers.kleinanzeigen import KleinanzeigenScraper
from services.telegram_service import TelegramService
from storage import SeenListings

# Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("wohnungsmonitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# Logging für externe Bibliotheken dämpfen
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


def check_all_platforms() -> None:
    """Prüft alle Plattformen auf neue Inserate und sendet Benachrichtigungen."""
    logger.info("=" * 60)
    logger.info("Starte Prüfung aller Plattformen...")

    scrapers = [
        ImmoScoutScraper(),
        ImmoweltScraper(),
        KleinanzeigenScraper(),
    ]

    seen = SeenListings()
    telegram = TelegramService()

    new_count = 0
    error_count = 0

    for scraper in scrapers:
        try:
            logger.info(f"Scrape {scraper.name}...")
            listings = scraper.fetch_listings()
            logger.info(f"{scraper.name}: {len(listings)} relevante Inserate gefunden")

            for listing in listings:
                key = listing.unique_key()

                if not seen.is_new(key):
                    logger.debug(f"Bereits bekannt: {key}")
                    continue

                logger.info(f"NEU: [{listing.source}] {listing.title} – {listing.url}")

                # Telegram-Benachrichtigung senden
                sent = telegram.send_listing_notification(listing)
                if sent:
                    seen.mark_as_seen(key)
                    new_count += 1
                    logger.info(f"Telegram-Benachrichtigung gesendet für: {key}")
                else:
                    error_count += 1
                    logger.error(f"Telegram-Versand fehlgeschlagen für: {key}")

        except Exception as e:
            error_count += 1
            logger.error(f"Unerwarteter Fehler beim Scrapen von {scraper.name}: {e}", exc_info=True)

    logger.info(
        f"Prüfung abgeschlossen – {new_count} neue Inserate gemeldet, "
        f"{error_count} Fehler. "
        f"(Gesamt bekannte Inserate: {seen.count()})"
    )


def main() -> None:
    """Einstiegspunkt: Validierung, erste Prüfung, dann regelmäßiger Zeitplan."""
    logger.info("Wohnungs-Monitor startet...")

    # Konfiguration prüfen
    errors = config.validate_config()
    if errors:
        for err in errors:
            logger.error(f"Konfigurationsfehler: {err}")
        logger.error(
            "Bitte .env-Datei prüfen (Vorlage: .env.example). Script wird beendet."
        )
        sys.exit(1)

    logger.info(f"Prüfintervall: alle {config.CHECK_INTERVAL_MINUTES} Minuten")
    logger.info(
        f"Stadtteil-Filter: {'aktiv (Frankenberger Viertel & Burtscheid)' if config.FILTER_BY_NEIGHBORHOOD else 'inaktiv (ganz Aachen)'}"
    )

    # Startup-Benachrichtigung via Telegram
    telegram = TelegramService()
    telegram.send_startup_message(["ImmobilienScout24", "Immowelt", "Kleinanzeigen"])

    # Sofortige erste Prüfung beim Start
    check_all_platforms()

    # Zeitplan einrichten
    schedule.every(config.CHECK_INTERVAL_MINUTES).minutes.do(check_all_platforms)
    logger.info(f"Nächste Prüfung in {config.CHECK_INTERVAL_MINUTES} Minuten.")

    # Hauptloop
    while True:
        schedule.run_pending()
        time.sleep(30)  # alle 30 Sekunden auf fällige Tasks prüfen


if __name__ == "__main__":
    main()
