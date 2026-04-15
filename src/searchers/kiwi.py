"""
Kiwi Tequila API searcher.
Free API key: https://tequila.kiwi.com/portal/login
Free tier: 500 req/month — ampiamente sufficiente per uso giornaliero.
"""
import logging
import requests
from datetime import datetime, timezone

from src.models import Flight, Segment

logger = logging.getLogger(__name__)

TEQUILA_BASE = "https://api.tequila.kiwi.com/v2/search"
ORIGINS = ["CDG", "ORY"]
DESTINATION = "FUE"
SEARCH_DATE = "28/12/2026"
TARGET_DATE = "2026-12-28"
MIN_DEP_HOUR = 12  # partenza non prima delle 12:00
MAX_STOPS = 1


class KiwiSearcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"apikey": api_key}

    def search(self) -> list[Flight]:
        flights: list[Flight] = []
        for origin in ORIGINS:
            try:
                results = self._fetch(origin)
                flights.extend(results)
            except Exception as exc:
                logger.error("Kiwi: errore per %s → %s: %s", origin, DESTINATION, exc)
        return sorted(flights, key=lambda f: f.price)

    def _fetch(self, origin: str) -> list[Flight]:
        params = {
            "fly_from": origin,
            "fly_to": DESTINATION,
            "date_from": SEARCH_DATE,
            "date_to": SEARCH_DATE,
            "flight_type": "oneway",
            "adults": 1,
            "max_stopovers": MAX_STOPS,
            "curr": "EUR",
            "limit": 50,
            "sort": "price",
            "asc": 1,
        }
        resp = requests.get(TEQUILA_BASE, headers=self.headers, params=params, timeout=20)
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

            # Durata
            fly_duration = item.get("fly_duration", "")
            duration = self._parse_duration(item.get("duration", {}).get("total", 0))

            # Segmenti
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
                source="kiwi",
            )
        except Exception as exc:
            logger.debug("Kiwi: parsing fallito su item: %s", exc)
            return None

    @staticmethod
    def _parse_duration(total_seconds: int) -> str:
        if not total_seconds:
            return "N/D"
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        return f"{h}h{m:02d}m"
