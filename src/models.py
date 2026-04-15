from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Segment:
    origin: str
    destination: str
    departure: str   # ISO datetime string
    arrival: str     # ISO datetime string
    carrier: str
    flight_number: str


@dataclass
class Flight:
    origin: str           # CDG or ORY
    destination: str      # FUE
    departure: str        # HH:MM
    arrival: str          # HH:MM
    date: str             # YYYY-MM-DD
    duration: str         # e.g. "4h30m"
    stops: int
    price: float
    currency: str
    carrier: str
    segments: list[Segment] = field(default_factory=list)
    booking_url: str = ""
    source: str = ""      # "kiwi" or "amadeus"

    def __str__(self) -> str:
        stops_label = "diretto" if self.stops == 0 else f"{self.stops} scalo"
        return (
            f"{self.origin} → {self.destination}  "
            f"{self.departure} → {self.arrival}  "
            f"({self.duration}, {stops_label})  "
            f"{self.price:.0f} {self.currency}  "
            f"[{self.carrier}]"
        )
