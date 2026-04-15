"""
Skypicker public API — ex backend di Kiwi.com, senza API key.
Endpoint stabile e funzionante senza registrazione.
Documentazione non ufficiale: il parametro partner=picky è obbligatorio.
"""
import logging
import requests
from datetime import datetime, timezone

from src.models import Flight, Segment

logger = logging.getLogger(__name__)

SKYPICKER_BASE = "https://api.skypicker.com/flights"
ORIGINS = ["CDG", "ORY"]
DESTINATION = "FUE"
SEARCH_DATE = "28/12/2026"
TARGET_DATE = "2026-12-28"
MIN_DEP_HOUR = 12
MAX_STOPS = 1

# Headers per ridurre probabilità di rate-limit
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class SkypickerSearcher:
    """Cerca voli tramite l'API pubblica di Skypicker (Kiwi), senza API key."""

    def search(self) -> list[Flight]:
        flights: list[Flight] = []
        for origin in ORIGINS:
            try:
                results = self._fetch(origin)
                flights.extend(results)
                logger.info("Skypicker: %s → %s: %d voli", origin, DESTINATION, len(results))
            except Exception as exc:
                logger.error("Skypicker: errore per %s → %s: %s", origin, DESTINATION, exc)
        return sorted(flights, key=lambda f: f.price)

    def _fetch(self, origin: str) -> list[Flight]:
        params = {
            "flyFrom": origin,
            "to": DESTINATION,
            "dateFrom": SEARCH_DATE,
            "dateTo": SEARCH_DATE,
            "typeFlight": "oneway",
            "adults": 1,
            "maxstopovers": MAX_STOPS,
            "curr": "EUR",
            "limit": 200,           # max documentato
            "sort": "price",
            "asc": 1,
            "partner": "picky",
            "partner_market": "es",
            "dtimefrom": "12:00",   # filtro server-side: partenza >= 12:00
        }
        resp = requests.get(
            SKYPICKER_BASE, headers=_HEADERS, params=params, timeout=25
        )
        resp.raise_for_status()
        data = resp.json()

        flights: list[Flight] = []
        for item in data.get("data", []):
            flight = self._parse_item(item, origin)
            if flight:
                flights.append(flight)
        return flights

    def _parse_item(self, item: dict, origin: str) -> Flight | None:
        try:
            dep_ts = item["dTime"]
            arr_ts = item["aTime"]
            dep_dt = datetime.fromtimestamp(dep_ts, tz=timezone.utc).astimezone()
            arr_dt = datetime.fromtimestamp(arr_ts, tz=timezone.utc).astimezone()

            # Partenza >= 12:00 locale
            if dep_dt.hour < MIN_DEP_HOUR:
                return None

            # Arrivo stesso giorno
            if arr_dt.strftime("%Y-%m-%d") != TARGET_DATE:
                return None

            stops = len(item.get("route", [])) - 1
            if stops > MAX_STOPS:
                return None

            duration = self._parse_duration(item.get("duration", {}).get("total", 0))

            segments = []
            for leg in item.get("route", []):
                leg_dep = datetime.fromtimestamp(leg["dTime"], tz=timezone.utc).astimezone()
                leg_arr = datetime.fromtimestamp(leg["aTime"], tz=timezone.utc).astimezone()
                segments.append(Segment(
                    origin=leg.get("flyFrom", ""),
                    destination=leg.get("flyTo", ""),
                    departure=leg_dep.strftime("%H:%M"),
                    arrival=leg_arr.strftime("%H:%M"),
                    carrier=leg.get("airline", ""),
                    flight_number=leg.get("flight_no", ""),
                ))

            airlines = item.get("airlines", [])
            carrier = ", ".join(airlines) if airlines else "N/D"

            return Flight(
                origin=origin,
                destination=DESTINATION,
                departure=dep_dt.strftime("%H:%M"),
                arrival=arr_dt.strftime("%H:%M"),
                date=TARGET_DATE,
                duration=duration,
                stops=stops,
                price=float(item.get("price", 0)),
                currency="EUR",
                carrier=carrier,
                segments=segments,
                booking_url=item.get("deep_link", ""),
                source="skypicker",
            )
        except Exception as exc:
            logger.debug("Skypicker: parsing fallito su item: %s", exc)
            return None

    @staticmethod
    def _parse_duration(total_seconds: int) -> str:
        if not total_seconds:
            return "N/D"
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        return f"{h}h{m:02d}m"
