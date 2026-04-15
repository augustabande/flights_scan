"""
Amadeus Flight Offers Search API.
Credenziali gratuite: https://developers.amadeus.com
Usa la production API (Self-Service) — accesso gratuito senza approvazione per uso personale.
Endpoint production: https://api.amadeus.com
"""
import logging
import re
import requests
from datetime import datetime

from src.models import Flight, Segment

logger = logging.getLogger(__name__)

AUTH_URL = "https://api.amadeus.com/v1/security/oauth2/token"
SEARCH_URL = "https://api.amadeus.com/v2/shopping/flight-offers"
ORIGINS = ["CDG", "ORY"]
DESTINATION = "FUE"
TARGET_DATE = "2026-12-28"
MIN_DEP_HOUR = 12
MAX_STOPS = 1


class AmadeusSearcher:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None

    # ------------------------------------------------------------------
    def search(self) -> list[Flight]:
        flights: list[Flight] = []
        try:
            self._authenticate()
        except Exception as exc:
            logger.error("Amadeus: autenticazione fallita: %s", exc)
            return flights

        for origin in ORIGINS:
            try:
                results = self._fetch(origin)
                flights.extend(results)
            except Exception as exc:
                logger.error("Amadeus: errore per %s → %s: %s", origin, DESTINATION, exc)
        return sorted(flights, key=lambda f: f.price)

    # ------------------------------------------------------------------
    def _authenticate(self):
        resp = requests.post(AUTH_URL, data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }, timeout=15)
        resp.raise_for_status()
        self._token = resp.json()["access_token"]

    def _fetch(self, origin: str) -> list[Flight]:
        headers = {"Authorization": f"Bearer {self._token}"}
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": DESTINATION,
            "departureDate": TARGET_DATE,
            "adults": 1,
            "max": 50,
            "currencyCode": "EUR",
            "nonStop": "false",
        }
        resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=20)
        if resp.status_code == 204:
            return []
        resp.raise_for_status()
        data = resp.json()

        carriers_dict = data.get("dictionaries", {}).get("carriers", {})
        flights: list[Flight] = []
        for offer in data.get("data", []):
            flight = self._parse_offer(offer, origin, carriers_dict)
            if flight:
                flights.append(flight)
        return flights

    def _parse_offer(self, offer: dict, origin: str, carriers: dict) -> Flight | None:
        try:
            itinerary = offer["itineraries"][0]
            segs = itinerary["segments"]

            if len(segs) - 1 > MAX_STOPS:
                return None

            first = segs[0]
            last = segs[-1]

            dep_dt = datetime.fromisoformat(first["departure"]["at"])
            arr_dt = datetime.fromisoformat(last["arrival"]["at"])

            if dep_dt.hour < MIN_DEP_HOUR:
                return None

            if arr_dt.strftime("%Y-%m-%d") != TARGET_DATE:
                return None

            # Durata
            duration = self._iso_duration(itinerary.get("duration", ""))

            # Segmenti
            segments = []
            for s in segs:
                s_dep = datetime.fromisoformat(s["departure"]["at"])
                s_arr = datetime.fromisoformat(s["arrival"]["at"])
                segments.append(Segment(
                    origin=s["departure"]["iataCode"],
                    destination=s["arrival"]["iataCode"],
                    departure=s_dep.strftime("%H:%M"),
                    arrival=s_arr.strftime("%H:%M"),
                    carrier=carriers.get(s["carrierCode"], s["carrierCode"]),
                    flight_number=f"{s['carrierCode']}{s['number']}",
                ))

            carrier_codes = list({s["carrierCode"] for s in segs})
            carrier = ", ".join(carriers.get(c, c) for c in carrier_codes)
            price = float(offer["price"]["total"])

            return Flight(
                origin=origin,
                destination=DESTINATION,
                departure=dep_dt.strftime("%H:%M"),
                arrival=arr_dt.strftime("%H:%M"),
                date=TARGET_DATE,
                duration=duration,
                stops=len(segs) - 1,
                price=price,
                currency="EUR",
                carrier=carrier,
                segments=segments,
                booking_url=f"https://www.google.com/travel/flights?q=voli+{origin}+FUE+28+dicembre+2026",
                source="amadeus",
            )
        except Exception as exc:
            logger.debug("Amadeus: parsing fallito: %s", exc)
            return None

    @staticmethod
    def _iso_duration(iso: str) -> str:
        """Converte PT4H30M in 4h30m."""
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso)
        if not m:
            return "N/D"
        h = int(m.group(1) or 0)
        mins = int(m.group(2) or 0)
        return f"{h}h{mins:02d}m"
