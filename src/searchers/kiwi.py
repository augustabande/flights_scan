import logging
import requests
from datetime import datetime

from src.models import Flight, Segment

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search.json"
ORIGINS = ["CDG", "ORY"]
DESTINATION = "FUE"
TARGET_DATE = "2026-12-28"
MIN_DEP_HOUR = 12


class SerpApiSearcher:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self) -> list[Flight]:
        flights: list[Flight] = []
        for origin in ORIGINS:
            try:
                results = self._fetch(origin)
                flights.extend(results)
                logger.info("SerpAPI: %s → %s: %d voli", origin, DESTINATION, len(results))
            except Exception as exc:
                logger.error("SerpAPI: errore per %s → %s: %s", origin, DESTINATION, exc)
        return sorted(flights, key=lambda f: f.price)

    def _fetch(self, origin: str) -> list[Flight]:
        params = {
            "engine": "google_flights",
            "departure_id": origin,
            "arrival_id": DESTINATION,
            "outbound_date": TARGET_DATE,
            "currency": "EUR",
            "hl": "en",
            "type": "2",    # one way
            "stops": "2",   # max 1 stop (0=any, 1=nonstop, 2=1 stop or fewer)
            "api_key": self.api_key,
        }
        resp = requests.get(SERPAPI_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        flights: list[Flight] = []
        for item in data.get("best_flights", []) + data.get("other_flights", []):
            flight = self._parse_item(item, origin)
            if flight:
                flights.append(flight)
        return flights

    def _parse_item(self, item: dict, origin: str) -> Flight | None:
        try:
            segs = item.get("flights", [])
            if not segs:
                return None

            first = segs[0]
            last = segs[-1]

            dep_str = first["departure_airport"]["time"]   # "2026-12-28 13:00"
            arr_str = last["arrival_airport"]["time"]

            dep_dt = datetime.strptime(dep_str, "%Y-%m-%d %H:%M")
            arr_dt = datetime.strptime(arr_str, "%Y-%m-%d %H:%M")

            if dep_dt.hour < MIN_DEP_HOUR:
                return None
            if arr_dt.strftime("%Y-%m-%d") != TARGET_DATE:
                return None

            stops = len(segs) - 1
            total_min = item.get("total_duration", 0)
            duration = f"{total_min // 60}h{total_min % 60:02d}m"

            segments = []
            for s in segs:
                segments.append(Segment(
                    origin=s["departure_airport"]["id"],
                    destination=s["arrival_airport"]["id"],
                    departure=datetime.strptime(s["departure_airport"]["time"], "%Y-%m-%d %H:%M").strftime("%H:%M"),
                    arrival=datetime.strptime(s["arrival_airport"]["time"], "%Y-%m-%d %H:%M").strftime("%H:%M"),
                    carrier=s.get("airline", ""),
                    flight_number=s.get("flight_number", ""),
                ))

            airlines = list({s.get("airline", "") for s in segs})
            carrier = ", ".join(a for a in airlines if a)

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
                booking_url="https://www.google.com/travel/flights",
                source="serpapi",
            )
        except Exception as exc:
            logger.debug("SerpAPI: parsing fallito: %s", exc)
            return None