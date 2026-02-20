"""Scraper für ImmobilienScout24."""

import json
import logging
import re
from typing import Optional

from .base import BaseScraper, Listing

logger = logging.getLogger(__name__)

# IS24 durchsucht die Viertel separat und kombiniert die Ergebnisse
SEARCH_URLS = [
    # Frankenberger Viertel – 4+ Zimmer, Miete
    "https://www.immobilienscout24.de/Suche/de/nordrhein-westfalen/aachen/frankenberger-viertel/wohnung-mieten?numberofrooms=4.0-",
    # Burtscheid – 4+ Zimmer, Miete
    "https://www.immobilienscout24.de/Suche/de/nordrhein-westfalen/aachen/burtscheid/wohnung-mieten?numberofrooms=4.0-",
    # Fallback: ganz Aachen (wird durch Stadtteil-Filter nachgefiltert)
    "https://www.immobilienscout24.de/Suche/de/nordrhein-westfalen/aachen/wohnung-mieten?numberofrooms=4.0-",
]

BASE_URL = "https://www.immobilienscout24.de"


class ImmoScoutScraper(BaseScraper):
    name = "ImmobilienScout24"

    def fetch_listings(self) -> list[Listing]:
        all_listings: dict[str, Listing] = {}  # key -> Listing (Deduplizierung)

        for url in SEARCH_URLS:
            response = self._get(url)
            if not response:
                continue

            listings = self._parse_page(response.text, url)
            for listing in listings:
                # Nur Inserate in den Ziel-Stadtteilen, keine Duplikate
                if listing.is_in_target_neighborhood():
                    all_listings[listing.unique_key()] = listing

            # Nur Fallback-URL brauchen wir, wenn die spezifischen URLs leer sind
            if len(all_listings) > 0 and url == SEARCH_URLS[1]:
                break

        return list(all_listings.values())

    def _parse_page(self, html: str, source_url: str) -> list[Listing]:
        """Versucht zuerst JSON-Daten aus dem Script-Tag zu lesen, dann HTML-Fallback."""
        listings = self._parse_next_data(html)
        if listings:
            logger.debug(f"IS24: {len(listings)} Inserate via __NEXT_DATA__ gefunden")
            return listings

        listings = self._parse_html(html)
        if listings:
            logger.debug(f"IS24: {len(listings)} Inserate via HTML-Parsing gefunden")
            return listings

        logger.warning(
            f"IS24: Keine Inserate gefunden auf {source_url}. "
            "Möglicherweise blockiert oder Seitenstruktur geändert."
        )
        return []

    def _parse_next_data(self, html: str) -> list[Listing]:
        """Extrahiert Inserate aus dem eingebetteten __NEXT_DATA__ JSON (Next.js)."""
        soup = self._parse(html)
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script_tag or not script_tag.string:
            return []

        try:
            data = json.loads(script_tag.string)
        except json.JSONDecodeError:
            return []

        # Pfad durch den JSON-Baum zu den Suchergebnissen
        try:
            result_list = (
                data["props"]["pageProps"]["searchResult"]["resultListItems"]
            )
        except (KeyError, TypeError):
            # Alternativer Pfad (IS24 ändert die Struktur gelegentlich)
            result_list = self._find_result_list(data)

        if not result_list:
            return []

        listings = []
        for item in result_list:
            listing = self._parse_next_item(item)
            if listing:
                listings.append(listing)
        return listings

    def _find_result_list(self, data: dict) -> list:
        """Durchsucht rekursiv ein JSON-Objekt nach einer Liste von Inseraten."""
        if isinstance(data, dict):
            # Typische Schlüsselnamen bei IS24
            for key in ("resultListItems", "resultList", "listings", "exposees"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            for value in data.values():
                result = self._find_result_list(value)
                if result:
                    return result
        elif isinstance(data, list) and data:
            # Prüfe ob die Liste Inserat-ähnliche Objekte enthält
            first = data[0]
            if isinstance(first, dict) and any(
                k in first for k in ("id", "exposeeId", "title", "realEstate")
            ):
                return data
        return []

    def _parse_next_item(self, item: dict) -> Optional[Listing]:
        """Extrahiert ein Listing aus einem JSON-Objekt."""
        try:
            # IS24 verschachtelt die Daten oft unter "realEstate" oder direkt
            re_data = item.get("realEstate", item)
            listing_id = str(
                re_data.get("id") or re_data.get("exposeeId") or item.get("id", "")
            )
            if not listing_id:
                return None

            title = re_data.get("title", "")
            price_obj = re_data.get("price", {})
            price = (
                f"{price_obj.get('value', '')} {price_obj.get('currency', 'EUR')}"
                if price_obj
                else None
            )
            size = str(re_data.get("livingSpace", "")) + " m²" if re_data.get("livingSpace") else None
            rooms = str(re_data.get("numberOfRooms", "")) if re_data.get("numberOfRooms") else None

            addr = re_data.get("address", {})
            address_parts = filter(None, [
                addr.get("street", ""),
                addr.get("houseNumber", ""),
                addr.get("postcode", ""),
                addr.get("city", ""),
            ])
            address = " ".join(address_parts) or None

            url = f"{BASE_URL}/expose/{listing_id}"

            return Listing(
                id=listing_id,
                source="immoscout24",
                title=title or f"Inserat {listing_id}",
                url=url,
                price=price,
                size=size,
                rooms=rooms,
                address=address,
            )
        except Exception as e:
            logger.debug(f"IS24: Fehler beim Parsen eines JSON-Items: {e}")
            return None

    def _parse_html(self, html: str) -> list[Listing]:
        """HTML-Fallback: Parst Inserate direkt aus dem gerenderten HTML."""
        soup = self._parse(html)
        listings = []

        # IS24 verwendet article-Elemente mit data-id Attribut
        articles = soup.select("article[data-id]") or soup.select("li[data-id]")

        for article in articles:
            listing = self._parse_html_article(article)
            if listing:
                listings.append(listing)

        return listings

    def _parse_html_article(self, article) -> Optional[Listing]:
        """Extrahiert ein Listing aus einem HTML-Artikel-Element."""
        try:
            listing_id = article.get("data-id", "").strip()
            if not listing_id:
                return None

            # Titel
            title_el = article.select_one("h2, .result-list-entry__brand-title")
            title = title_el.get_text(strip=True) if title_el else f"Inserat {listing_id}"

            # Preis
            price_el = article.select_one(
                ".result-list-entry__primary-criterion .font-nowrap, "
                "[data-cy='price']"
            )
            price = price_el.get_text(strip=True) if price_el else None

            # Adresse
            addr_el = article.select_one(
                ".result-list-entry__address, .result-list-entry__map-link, "
                "[data-cy='location']"
            )
            address = addr_el.get_text(strip=True) if addr_el else None

            url = f"{BASE_URL}/expose/{listing_id}"

            return Listing(
                id=listing_id,
                source="immoscout24",
                title=title,
                url=url,
                price=price,
                address=address,
            )
        except Exception as e:
            logger.debug(f"IS24: Fehler beim Parsen eines HTML-Artikels: {e}")
            return None
