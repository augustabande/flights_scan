"""
Notifier: invia risultati via ntfy.sh (push nativa iOS/Android, free, no account)
e opzionalmente via email SMTP come fallback.

Setup ntfy.sh:
  1. Installa l'app ntfy su iOS o Android.
  2. Scegli un topic privato (stringa casuale, es: "flight-fue-2026-xk7q").
  3. Iscriviti al topic nell'app.
  4. Imposta NTFY_TOPIC nel secret di GitHub.
"""
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from src.models import Flight

logger = logging.getLogger(__name__)

NTFY_BASE = "https://ntfy.sh"


class Notifier:
    def __init__(
        self,
        ntfy_topic: str | None = None,
        email_to: str | None = None,
        email_from: str | None = None,
        email_password: str | None = None,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 465,
    ):
        self.ntfy_topic = ntfy_topic
        self.email_to = email_to
        self.email_from = email_from
        self.email_password = email_password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    # ------------------------------------------------------------------
    def send(self, flights: list[Flight], run_date: str):
        body_text, body_html = self._build_body(flights, run_date)
        title = self._build_title(flights)

        if self.ntfy_topic:
            self._send_ntfy(title, body_text, flights)
        else:
            logger.warning("NTFY_TOPIC non configurato — push notification saltata.")

        if self.email_to and self.email_from and self.email_password:
            self._send_email(title, body_html, run_date)
        else:
            logger.info("Email non configurata — saltata.")

    # ------------------------------------------------------------------
    def _build_title(self, flights: list[Flight]) -> str:
        if not flights:
            return "CDG/ORY → FUE 28/12/2026 — Nessun volo trovato"
        best = flights[0]
        return (
            f"CDG/ORY → FUE 28/12  {best.price:.0f}€  "
            f"{best.departure}→{best.arrival}  {best.carrier}"
        )

    def _build_body(self, flights: list[Flight], run_date: str) -> tuple[str, str]:
        if not flights:
            text = (
                f"Scansione del {run_date}\n"
                "Nessun volo trovato con i criteri impostati:\n"
                "  - CDG o ORY → FUE\n"
                "  - 28 dicembre 2026, partenza >= 12:00\n"
                "  - Max 1 scalo, arrivo stesso giorno\n"
            )
            html = f"<p><b>Scansione del {run_date}</b></p><p>Nessun volo trovato.</p>"
            return text, html

        lines_text = [f"Scansione del {run_date} — {len(flights)} volo/i trovato/i\n"]
        rows_html = []

        for i, f in enumerate(flights, 1):
            stops_label = "diretto" if f.stops == 0 else f"{f.stops} scalo"
            seg_detail = ""
            if f.stops > 0 and f.segments:
                via = [s.destination for s in f.segments[:-1]]
                seg_detail = f"  via {', '.join(via)}"

            line = (
                f"{i}. {f.origin} → {f.destination}  "
                f"{f.departure} → {f.arrival}  "
                f"({f.duration}, {stops_label}{seg_detail})  "
                f"{f.price:.0f}€  [{f.carrier}]"
            )
            lines_text.append(line)
            if f.booking_url:
                lines_text.append(f"   Prenota: {f.booking_url}")

            rows_html.append(
                f"<tr>"
                f"<td>{f.origin}</td>"
                f"<td>{f.departure} → {f.arrival}</td>"
                f"<td>{f.duration}</td>"
                f"<td>{stops_label}{seg_detail}</td>"
                f"<td>{f.carrier}</td>"
                f"<td><b>{f.price:.0f}€</b></td>"
                f"<td><a href='{f.booking_url}'>Prenota</a></td>"
                f"</tr>"
            )

        text = "\n".join(lines_text)
        html = (
            f"<p><b>Scansione del {run_date}</b> — {len(flights)} volo/i</p>"
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<tr><th>Da</th><th>Orari</th><th>Durata</th><th>Scali</th><th>Compagnia</th><th>Prezzo</th><th>Link</th></tr>"
            + "".join(rows_html)
            + "</table>"
        )
        return text, html

    # ------------------------------------------------------------------
    def _send_ntfy(self, title: str, body: str, flights: list[Flight]):
        url = f"{NTFY_BASE}/{self.ntfy_topic}"
        priority = "high" if flights else "default"
        # Tronca il body per ntfy (max ~4096 chars)
        payload = body[:3800]
        try:
            resp = requests.post(
                url,
                data=payload.encode("utf-8"),
                headers={
                    "Title": title.encode("utf-8"),
                    "Priority": priority,
                    "Tags": "airplane,eu",
                },
                timeout=15,
            )
            resp.raise_for_status()
            logger.info("ntfy.sh: notifica inviata al topic '%s'.", self.ntfy_topic)
        except Exception as exc:
            logger.error("ntfy.sh: invio fallito: %s", exc)

    def _send_email(self, subject: str, body_html: str, run_date: str):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.email_from
        msg["To"] = self.email_to
        msg.attach(MIMEText(body_html, "html"))
        ctx = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ctx) as server:
                server.login(self.email_from, self.email_password)
                server.sendmail(self.email_from, self.email_to, msg.as_string())
            logger.info("Email inviata a %s.", self.email_to)
        except Exception as exc:
            logger.error("Email: invio fallito: %s", exc)
