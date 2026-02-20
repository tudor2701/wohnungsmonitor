"""Basisklassen für alle Scraper."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import FILTER_BY_NEIGHBORHOOD, NEIGHBORHOOD_KEYWORDS

logger = logging.getLogger(__name__)

# Realistischer Browser-Header, um Anti-Bot-Maßnahmen zu umgehen
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class Listing:
    """Repräsentiert ein einzelnes Wohnungsinserat."""

    id: str                           # Eindeutige ID zur Deduplizierung
    source: str                       # "immoscout24", "immowelt", "kleinanzeigen"
    title: str
    url: str
    price: Optional[str] = None       # Monatliche Miete
    size: Optional[str] = None        # Wohnfläche in m²
    rooms: Optional[str] = None       # Zimmeranzahl
    address: Optional[str] = None     # Adresse / Standort
    description: Optional[str] = None # Kurzbeschreibung
    image_url: Optional[str] = None
    found_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def unique_key(self) -> str:
        """Eindeutiger Schlüssel zur Deduplizierung über alle Quellen."""
        return f"{self.source}:{self.id}"

    def is_in_target_neighborhood(self) -> bool:
        """Prüft ob das Inserat aus einem der Ziel-Stadtteile stammt."""
        if not FILTER_BY_NEIGHBORHOOD:
            return True
        text = " ".join(
            part.lower()
            for part in [self.title, self.address, self.description]
            if part
        )
        return any(kw in text for kw in NEIGHBORHOOD_KEYWORDS)


class BaseScraper(ABC):
    """Abstrakte Basisklasse für alle Plattform-Scraper."""

    name: str = "Unbekannte Plattform"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _get(self, url: str, delay: float = 1.5, **kwargs) -> Optional[requests.Response]:
        """Führt einen GET-Request mit Fehlerbehandlung und Wartezeit aus."""
        time.sleep(delay)
        try:
            response = self.session.get(url, timeout=15, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                logger.warning(f"{self.name}: Zugriff verweigert (403) – möglicherweise blockiert. URL: {url}")
            else:
                logger.error(f"{self.name}: HTTP-Fehler bei {url}: {e}")
        except requests.exceptions.Timeout:
            logger.error(f"{self.name}: Timeout bei {url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"{self.name}: Fehler bei {url}: {e}")
        return None

    def _parse(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    @abstractmethod
    def fetch_listings(self) -> list[Listing]:
        """Holt aktuelle Inserate und gibt gefilterte Liste zurück."""
        ...
