"""Sendet Telegram-Benachrichtigungen über neue Wohnungsinserate."""

import logging
from typing import Optional

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from scrapers.base import Listing

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Quell-Emojis für visuelle Unterscheidung
SOURCE_EMOJI = {
    "immoscout24": "🏡",
    "immowelt": "🏘️",
    "kleinanzeigen": "📋",
}


class TelegramService:
    """Sendet Nachrichten über die Telegram Bot API."""

    def send_listing_notification(
        self, listing: Listing, contact_message: Optional[str] = None
    ) -> bool:
        """
        Sendet eine vollständige Benachrichtigung für ein neues Inserat.
        Gibt True zurück, wenn die Nachricht erfolgreich gesendet wurde.
        """
        text = self._format_message(listing, contact_message)
        return self._send_message(text)

    def send_startup_message(self, platforms: list[str]) -> None:
        """Sendet eine Bestätigungsnachricht beim Start des Scripts."""
        text = (
            "✅ *Wohnungs-Monitor gestartet*\n\n"
            f"Ich überwache jetzt:\n"
            + "\n".join(f"• {p}" for p in platforms)
            + "\n\nIch melde mich, sobald neue 4-Zimmer-Wohnungen in "
            "Frankenberger Viertel oder Burtscheid auftauchen!"
        )
        self._send_message(text)

    def send_error_notification(self, error_msg: str) -> None:
        """Sendet eine Fehlermeldung (für kritische Fehler)."""
        text = f"⚠️ *Wohnungs-Monitor Fehler*\n\n`{error_msg}`"
        self._send_message(text)

    def _format_message(self, listing: Listing, contact_message: Optional[str]) -> str:
        """Formatiert die Telegram-Nachricht mit Markdown."""
        emoji = SOURCE_EMOJI.get(listing.source, "🏠")
        source_name = listing.source.replace("immoscout24", "ImmobilienScout24").replace(
            "immowelt", "Immowelt"
        ).replace("kleinanzeigen", "Kleinanzeigen")

        lines = [
            f"{emoji} *Neue Wohnung auf {source_name}\\!*",
            "",
            f"*{self._escape(listing.title)}*",
            "",
        ]

        if listing.address:
            lines.append(f"📍 {self._escape(listing.address)}")
        if listing.price:
            lines.append(f"💶 {self._escape(listing.price)}")
        if listing.size:
            lines.append(f"📐 {self._escape(listing.size)}")
        if listing.rooms:
            lines.append(f"🚪 {self._escape(listing.rooms)} Zimmer")

        lines += [
            "",
            f"🔗 [Zum Inserat]({listing.url})",
        ]

        if contact_message:
            lines += [
                "",
                "─" * 30,
                "",
                "📝 *Vorgeschlagene Kontaktnachricht:*",
                "",
                f"```\n{contact_message}\n```",
            ]

        return "\n".join(lines)

    def _escape(self, text: str) -> str:
        """Escaped Sonderzeichen für Telegram MarkdownV2."""
        special_chars = r"_*[]()~`>#+-=|{}.!"
        for char in special_chars:
            text = text.replace(char, f"\\{char}")
        return text

    def _send_message(self, text: str) -> bool:
        """Sendet eine Nachricht via Telegram Bot API."""
        url = f"{TELEGRAM_API_BASE}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.debug("Telegram: Nachricht erfolgreich gesendet")
            return True
        except requests.exceptions.HTTPError as e:
            # Bei Markdown-Fehlern: Nachricht als Plaintext nochmal versuchen
            if e.response is not None and e.response.status_code == 400:
                logger.warning("Telegram: Markdown-Fehler, versuche Plaintext...")
                return self._send_plain(text)
            logger.error(f"Telegram: HTTP-Fehler: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram: Verbindungsfehler: {e}")

        return False

    def _send_plain(self, text: str) -> bool:
        """Fallback: Sendet Nachricht ohne Markdown-Formatierung."""
        # Entferne Markdown-Escape-Zeichen
        import re
        plain_text = re.sub(r"\\([_*\[\]()~`>#+=|{}.!-])", r"\1", text)
        plain_text = re.sub(r"[*_`]", "", plain_text)

        url = f"{TELEGRAM_API_BASE}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": plain_text[:4096],  # Telegram-Limit
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram: Plaintext-Fallback fehlgeschlagen: {e}")
            return False
