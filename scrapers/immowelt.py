"""Scraper für Immowelt."""

import json
import logging
from typing import Optional

from .base import BaseScraper, Listing

logger = logging.getLogger(__name__)

# Immowelt unterstützt direkte Stadtteil-Suche via URL-Parameter
SEARCH_URLS = [
    # Frankenberger Viertel
    "https://www.immowelt.de/liste/aachen/wohnungen/mieten?rooms_from=4&lage=frankenberger-viertel&sort=createdAt",
    # Burtscheid
    "https://www.immowelt.de/liste/aachen/wohnungen/mieten?rooms_from=4&lage=burtscheid&sort=createdAt",
    # Fallback: ganz Aachen
    "https://www.immowelt.de/liste/aachen/wohnungen/mieten?rooms_from=4&sort=createdAt",
]

BASE_URL = "https://www.immowelt.de"


class ImmoweltScraper(BaseScraper):
    name = "Immowelt"

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
        """Versucht JSON-Daten, dann HTML-Fallback."""
        listings = self._parse_next_data(html)
        if listings:
            logger.debug(f"Immowelt: {len(listings)} Inserate via __NEXT_DATA__ gefunden")
            return listings

        listings = self._parse_html(html)
        if listings:
            logger.debug(f"Immowelt: {len(listings)} Inserate via HTML-Parsing gefunden")
            return listings

        logger.warning("Immowelt: Keine Inserate gefunden – möglicherweise blockiert oder Seitenstruktur geändert.")
        return []

    def _parse_next_data(self, html: str) -> list[Listing]:
        """Extrahiert Inserate aus dem __NEXT_DATA__ JSON."""
        soup = self._parse(html)
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script_tag or not script_tag.string:
            return []

        try:
            data = json.loads(script_tag.string)
        except json.JSONDecodeError:
            return []

        # Suche nach EstateItems oder ähnlichen Listen im JSON
        estate_list = self._find_estate_list(data)
        if not estate_list:
            return []

        listings = []
        for item in estate_list:
            listing = self._parse_estate_item(item)
            if listing:
                listings.append(listing)
        return listings

    def _find_estate_list(self, data) -> list:
        """Durchsucht rekursiv nach Immowelt-Inseratlisten."""
        if isinstance(data, dict):
            for key in ("estateItems", "estates", "items", "results", "listings"):
                if key in data and isinstance(data[key], list) and data[key]:
                    return data[key]
            for value in data.values():
                result = self._find_estate_list(value)
                if result:
                    return result
        elif isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict) and any(
                k in first for k in ("globalObjectId", "id", "estateId", "title")
            ):
                return data
        return []

    def _parse_estate_item(self, item: dict) -> Optional[Listing]:
        """Extrahiert ein Listing aus einem Immowelt JSON-Objekt."""
        try:
            listing_id = str(
                item.get("globalObjectId") or item.get("estateId") or item.get("id", "")
            )
            if not listing_id:
                return None

            title = item.get("title", "") or item.get("name", "") or f"Inserat {listing_id}"

            # Preis
            price_data = item.get("prices", {}) or item.get("price", {})
            rent = price_data.get("rent") or price_data.get("value")
            price = f"{rent} €" if rent else None

            # Größe und Zimmer
            area = item.get("areas", {}) or {}
            size_val = area.get("livingArea") or item.get("livingArea")
            size = f"{size_val} m²" if size_val else None
            rooms_val = item.get("rooms") or item.get("numberOfRooms")
            rooms = str(rooms_val) if rooms_val else None

            # Adresse
            loc = item.get("location", {}) or {}
            address_parts = filter(None, [
                loc.get("street", ""),
                loc.get("houseNumber", ""),
                loc.get("zipCode", ""),
                loc.get("city", ""),
                loc.get("district", ""),
            ])
            address = " ".join(address_parts) or item.get("locationLabel") or None

            # URL
            url_path = item.get("detailUrl") or item.get("url") or f"/expose/wohnung-mieten/{listing_id}"
            url = url_path if url_path.startswith("http") else f"{BASE_URL}{url_path}"

            return Listing(
                id=listing_id,
                source="immowelt",
                title=title,
                url=url,
                price=price,
                size=size,
                rooms=rooms,
                address=address,
            )
        except Exception as e:
            logger.debug(f"Immowelt: Fehler beim Parsen eines JSON-Items: {e}")
            return None

    def _parse_html(self, html: str) -> list[Listing]:
        """HTML-Fallback-Parser für Immowelt."""
        soup = self._parse(html)
        listings = []

        # Immowelt verwendet verschiedene Selektoren je nach Seitenversion
        items = (
            soup.select("div[data-testid='EstateItem']")
            or soup.select("article.EstateItem")
            or soup.select("[class*='EstateItem']")
            or soup.select("div[class*='estateitem']")
        )

        for item in items:
            listing = self._parse_html_item(item)
            if listing:
                listings.append(listing)

        return listings

    def _parse_html_item(self, item) -> Optional[Listing]:
        """Extrahiert ein Listing aus einem HTML-Element."""
        try:
            # ID aus dem Link extrahieren
            link = item.select_one("a[href*='/expose/']") or item.select_one("a[href]")
            if not link:
                return None

            href = link.get("href", "")
            # ID aus dem Pfad extrahieren (z.B. /expose/wohnung-mieten/12345)
            import re
            id_match = re.search(r"(\d{5,})", href)
            listing_id = id_match.group(1) if id_match else href.split("/")[-1]
            if not listing_id:
                return None

            url = href if href.startswith("http") else f"{BASE_URL}{href}"

            # Titel
            title_el = item.select_one("h2, h3, [class*='title'], [class*='Title']")
            title = title_el.get_text(strip=True) if title_el else f"Inserat {listing_id}"

            # Preis
            price_el = item.select_one(
                "[class*='price'], [class*='Price'], [data-testid*='price']"
            )
            price = price_el.get_text(strip=True) if price_el else None

            # Adresse
            addr_el = item.select_one(
                "[class*='location'], [class*='Location'], [class*='address'], [class*='Address']"
            )
            address = addr_el.get_text(strip=True) if addr_el else None

            return Listing(
                id=listing_id,
                source="immowelt",
                title=title,
                url=url,
                price=price,
                address=address,
            )
        except Exception as e:
            logger.debug(f"Immowelt: Fehler beim Parsen eines HTML-Items: {e}")
            return None
