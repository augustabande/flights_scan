# Flight Monitor — CDG/ORY → FUE, 28 dicembre 2026

Monitora ogni giorno i voli da Parigi (CDG e ORY) a Fuerteventura (FUE) per il 28 dicembre 2026,
con partenza dalle 12:00, massimo 1 scalo e arrivo entro la sera.
Ogni mattina alle 07:00 CET ricevi una notifica push con i migliori prezzi trovati.

## Architettura

- **Fonti dati**: Skypicker public API (primaria, no API key) + Amadeus Flight Offers API (secondaria)
- **Scheduler**: GitHub Actions, cron `0 6 * * *` (07:00 CET)
- **Notifiche**: ntfy.sh (push iOS/Android, gratuita, zero config)
- **Storage**: snapshot JSON giornaliero in `history/` committato nel repo

## Setup — 10 minuti

### 1. Fork/clone del repository su GitHub

```bash
git clone https://github.com/TUO_USERNAME/flight-monitor.git
cd flight-monitor
```

### 2. Ottieni le API key

**Skypicker (nessuna chiave necessaria)**
La fonte primaria usa `api.skypicker.com` — endpoint pubblico, nessuna registrazione.

**Amadeus (opzionale ma consigliata per dati aggiuntivi)**
1. Vai su https://developers.amadeus.com
2. Registrati e crea una Self-Service app
3. Prendi le credenziali dalla sezione "Production"

### 3. Configura l'app ntfy

1. Installa l'app **ntfy** su iOS o Android (gratuita)
2. Scegli un topic privato univoco, es: `fue-flights-k7q2m9x`
3. Apri l'app, tap su "+" e aggiungi il tuo topic
4. Da quel momento riceverai le notifiche

### 4. Aggiungi i GitHub Secrets

Nel tuo repository: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valore |
|--------|--------|
| `AMADEUS_CLIENT_ID` | (opzionale) |
| `AMADEUS_SECRET` | (opzionale) |
| `NTFY_TOPIC` | es: `fue-flights-k7q2m9x` |
| `EMAIL_TO` | (opzionale) la tua email |
| `EMAIL_FROM` | (opzionale) gmail mittente |
| `EMAIL_PASSWORD` | (opzionale) App Password Gmail |

### 5. Abilita i permessi di write per Actions

**Settings → Actions → General → Workflow permissions → Read and write permissions**

### 6. Test immediato

Vai su **Actions → Flight Monitor → Run workflow** per eseguire subito il primo run
e verificare che tutto funzioni prima di aspettare le 07:00 di domani.

## Test locale

```bash
cp .env.example .env
# Compila .env con le tue chiavi

pip install -r requirements.txt
export $(cat .env | xargs)
python -m src.main
```

## Criteri di ricerca

- Origini: CDG (Charles de Gaulle) e ORY (Orly)
- Destinazione: FUE (Fuerteventura)
- Data: 28 dicembre 2026
- Orario partenza: >= 12:00
- Arrivo: stesso giorno (28 dicembre)
- Scali massimi: 1
- Ordinamento: prezzo crescente

## Storico prezzi

Ogni run salva un file in `history/YYYY-MM-DD.json` con tutti i voli trovati e il miglior prezzo del giorno.
Puoi usarlo per visualizzare l'andamento dei prezzi nel tempo.

## Note

Il tool segnala anche la variazione di prezzo rispetto al giorno precedente nel log di GitHub Actions.
