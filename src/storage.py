"""
Storage: salva ogni giorno uno snapshot JSON nella cartella history/.
Utile per tracciare l'evoluzione dei prezzi nel tempo.
"""
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.models import Flight

logger = logging.getLogger(__name__)
HISTORY_DIR = Path("history")


def save_snapshot(flights: list[Flight], run_date: str):
    HISTORY_DIR.mkdir(exist_ok=True)
    path = HISTORY_DIR / f"{run_date}.json"
    payload = {
        "run_date": run_date,
        "run_timestamp": datetime.utcnow().isoformat() + "Z",
        "count": len(flights),
        "best_price": flights[0].price if flights else None,
        "flights": [_flight_to_dict(f) for f in flights],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Snapshot salvato: %s (%d voli)", path, len(flights))


def load_previous_best(run_date: str) -> float | None:
    """Restituisce il miglior prezzo dello snapshot precedente, se disponibile."""
    snapshots = sorted(HISTORY_DIR.glob("*.json"))
    for snap in reversed(snapshots):
        if snap.stem < run_date:
            try:
                data = json.loads(snap.read_text(encoding="utf-8"))
                return data.get("best_price")
            except Exception:
                continue
    return None


def _flight_to_dict(f: Flight) -> dict:
    d = asdict(f)
    return d
