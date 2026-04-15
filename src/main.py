"""
Orchestratore principale.
Eseguito ogni mattina da GitHub Actions alle 07:00 CET.

Variabili d'ambiente richieste (GitHub Secrets):
  KIWI_API_KEY       — da tequila.kiwi.com (obbligatorio)
  AMADEUS_CLIENT_ID  — da developers.amadeus.com (opzionale)
  AMADEUS_SECRET     — da developers.amadeus.com (opzionale)
  NTFY_TOPIC         — topic ntfy.sh personale (obbligatorio per push)
  EMAIL_TO           — indirizzo destinatario (opzionale)
  EMAIL_FROM         — account Gmail mittente (opzionale)
  EMAIL_PASSWORD     — App Password Gmail (opzionale)
"""
import logging
import os
import sys
from datetime import date

from src.models import Flight
from src.notifier import Notifier
from src.storage import load_previous_best, save_snapshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    run_date = date.today().isoformat()
    logger.info("=== Flight Monitor avviato — %s ===", run_date)

    flights: list[Flight] = []

    # --- Kiwi (fonte primaria) ---
    kiwi_key = os.getenv("KIWI_API_KEY")
    if kiwi_key:
        from src.searchers.kiwi import KiwiSearcher
        logger.info("Kiwi: ricerca in corso...")
        try:
            kiwi_results = KiwiSearcher(kiwi_key).search()
            logger.info("Kiwi: trovati %d voli.", len(kiwi_results))
            flights.extend(kiwi_results)
        except Exception as exc:
            logger.error("Kiwi: errore: %s", exc)
    else:
        logger.warning("KIWI_API_KEY non impostata — sorgente Kiwi saltata.")

    # --- Amadeus (fonte secondaria) ---
    amadeus_id = os.getenv("AMADEUS_CLIENT_ID")
    amadeus_secret = os.getenv("AMADEUS_SECRET")
    if amadeus_id and amadeus_secret:
        from src.searchers.amadeus import AmadeusSearcher
        logger.info("Amadeus: ricerca in corso...")
        try:
            amadeus_results = AmadeusSearcher(amadeus_id, amadeus_secret).search()
            logger.info("Amadeus: trovati %d voli.", len(amadeus_results))
            flights.extend(amadeus_results)
        except Exception as exc:
            logger.error("Amadeus: errore: %s", exc)
    else:
        logger.info("Credenziali Amadeus non impostate — sorgente Amadeus saltata.")

    # --- Deduplication (stesso prezzo + orario + compagnia) ---
    seen: set[tuple] = set()
    unique_flights: list[Flight] = []
    for f in flights:
        key = (f.origin, f.departure, f.arrival, f.carrier, round(f.price))
        if key not in seen:
            seen.add(key)
            unique_flights.append(f)

    unique_flights.sort(key=lambda f: f.price)
    logger.info("Totale voli unici dopo deduplicazione: %d", len(unique_flights))

    # --- Segnala variazione prezzo ---
    prev_best = load_previous_best(run_date)
    if prev_best and unique_flights:
        diff = unique_flights[0].price - prev_best
        if diff < 0:
            logger.info("Prezzo migliorato di %.0f€ rispetto a ieri.", abs(diff))
        elif diff > 0:
            logger.info("Prezzo aumentato di %.0f€ rispetto a ieri.", diff)

    # --- Salva snapshot ---
    save_snapshot(unique_flights, run_date)

    # --- Notifica ---
    notifier = Notifier(
        ntfy_topic=os.getenv("NTFY_TOPIC"),
        email_to=os.getenv("EMAIL_TO"),
        email_from=os.getenv("EMAIL_FROM"),
        email_password=os.getenv("EMAIL_PASSWORD"),
    )
    notifier.send(unique_flights, run_date)

    logger.info("=== Flight Monitor completato ===")
    sys.exit(0)


if __name__ == "__main__":
    main()
