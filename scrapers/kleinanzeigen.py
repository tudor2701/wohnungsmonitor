"""Scraper für Kleinanzeigen (ehemals eBay Kleinanzeigen)."""

import logging
import re
from typing import Optional

from .base import BaseScraper, Listing

logger = logging.getLogger(__name__)

# Kleinanzeigen: c203 = Wohnungen zur Miete, l1788 = Aachen
# Die Zimmerfilter werden über URL-Parameter gesteuert
SEARCH_URLS = [
    # 4 Zimmer, Miete, Aachen – Frankenberger Viertel per Keyword
    "https://www.kleinanzeigen.de/s-wohnung-mieten/aachen/frankenberger/k0c203l1788",
    # Burtscheid
    "https://www.kleinanzeigen.de/s-wohnung-mieten/aachen/burtscheid/k0c203l1788",
    # Fallback: alle Mietwohnungen Aachen
    "https://www.kleinanzeigen.de/s-wohnung-mieten/aachen/k0c203l1788",
]

BASE_URL = "https://www.kleinanzeigen.de"


class KleinanzeigenScraper(BaseScraper):
    name = "Kleinanzeigen"

    def __init__(self):
        super().__init__()
        # Kleinanzeigen blockiert ohne Referer-Header manchmal
        self.session.headers.update({
            "Referer": "https://www.kleinanzeigen.de/",
        })

    def fetch_listings(self) -> list[Listing]:
        all_listings: dict[str, Listing] = {}

        for url in SEARCH_URLS:
            response = self._get(url)
            if not response:
                continue

            listings = self._parse_page(response.text)
            for listing in listings:
                if listing.is_in_target_neighborhood():
                    all_listings[listing.unique_key()] = listing

            if len(all_listings) > 0 and url == SEARCH_URLS[1]:
                break

        return list(all_listings.values())

    def _parse_page(self, html: str) -> list[Listing]:
        soup = self._parse(html)
        listings = []

        # Kleinanzeigen rendert Inserate in article-Elementen mit data-adid
        articles = soup.select("article.aditem[data-adid]")

        if not articles:
            # Fallback: suche nach li-Elementen mit aditem-Klasse
            articles = soup.select("li[data-adid]") or soup.select("[data-adid]")

        if not articles:
            logger.warning("Kleinanzeigen: Keine Artikel gefunden – möglicherweise blockiert oder Seitenstruktur geändert.")
            return []

        for article in articles:
            listing = self._parse_article(article)
            if listing and self._has_enough_rooms(listing):
                listings.append(listing)

        logger.debug(f"Kleinanzeigen: {len(listings)} passende Inserate auf dieser Seite")
        return listings

    def _parse_article(self, article) -> Optional[Listing]:
        """Extrahiert ein Listing aus einem Kleinanzeigen-Artikel-Element."""
        try:
            listing_id = article.get("data-adid", "").strip()
            if not listing_id:
                return None

            # Titel & Link
            title_link = (
                article.select_one("a.ellipsis")
                or article.select_one("h2 a")
                or article.select_one("a[href*='/s-anzeige/']")
            )
            if not title_link:
                return None

            title = title_link.get_text(strip=True)
            href = title_link.get("href", "")
            url = href if href.startswith("http") else f"{BASE_URL}{href}"

            # Preis
            price_el = (
                article.select_one(".aditem-main--top--right")
                or article.select_one("[class*='price']")
            )
            price = price_el.get_text(strip=True) if price_el else None
            # "VB" oder "Zu verschenken" ignorieren bei Mietwohnungen ist unüblich,
            # trotzdem: wenn kein Preis → behalten (könnte relevantes Inserat sein)

            # Adresse / Ort
            location_el = (
                article.select_one(".aditem-main--top--left")
                or article.select_one("[class*='location']")
            )
            address = location_el.get_text(strip=True) if location_el else None

            # Kurzbeschreibung
            desc_el = (
                article.select_one(".aditem-main--middle--description")
                or article.select_one("p.description")
            )
            description = desc_el.get_text(strip=True) if desc_el else None

            return Listing(
                id=listing_id,
                source="kleinanzeigen",
                title=title,
                url=url,
                price=price,
                address=address,
                description=description,
            )
        except Exception as e:
            logger.debug(f"Kleinanzeigen: Fehler beim Parsen eines Artikels: {e}")
            return None

    def _has_enough_rooms(self, listing: Listing) -> bool:
        """
        Prüft ob das Inserat (laut Titel/Beschreibung) mindestens 4 Zimmer hat.
        Kleinanzeigen hat keinen zuverlässigen URL-Filter für Zimmeranzahl.
        """
        text = f"{listing.title} {listing.description or ''}".lower()

        # Suche nach Mustern wie "4 zimmer", "4-zimmer", "4zi", "4 zi.", "vierzimmer"
        patterns = [
            r"\b[4-9]\s*[-]?\s*zimmer",
            r"\b[4-9]\s*zi\b",
            r"\b[4-9]\s*zkb\b",  # Zimmer, Küche, Bad
            r"\bvierzimmer",
            r"\b[4-9]\s*z\.\s*wohnung",
        ]
        if any(re.search(p, text) for p in patterns):
            return True

        # Wenn keine Zimmerinfo im Text → nicht ausschließen
        # (könnte trotzdem relevant sein, besser falsch-positiv als falsch-negativ)
        no_room_info = not re.search(r"\b\d+\s*[-]?\s*zimmer|\b\d+\s*zi\b", text)
        return no_room_info
