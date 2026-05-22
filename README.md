# The Triad PC — Night Crew

Portale web in stile “dark tech / neon arancio” per scoprire eventi e contenuti editoriali, con chat “Gabo AI” (backend Python + OpenRouter).

## Requisiti

- .NET SDK 10
- Python 3

## Configurazione

Crea un file `.env` (non committarlo):

```bash
cp .envexample .env
```

Compila `.env` con le variabili richieste.

## Avvio in locale

### Avvia backend chat (Gabo AI)

```bash
python3 "Gabo AI/GaboAI.py" --serve --host 127.0.0.1 --port 8080
```

Healthcheck:

```bash
curl http://127.0.0.1:8080/health
```

### Avvia il portale (Blazor Server)

```bash
cd "The Triad PC"
dotnet restore
dotnet run --launch-profile http
```

Apri l’URL indicato in console (es. `http://localhost:5273/`).

## Troubleshooting

### `Address already in use` / `net::ERR_ABORTED`

Se una porta è già occupata (es. `5273` o `8080`), il server non parte e il browser può mostrare `net::ERR_ABORTED`.

Vedi chi sta usando la porta:

```bash
lsof -nP -iTCP:5273 -sTCP:LISTEN
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

Chiudi il processo (sostituisci `<PID>`):

```bash
kill <PID>
```

Oppure avvia su una porta diversa:

```bash
cd "The Triad PC"
dotnet run --launch-profile http --urls http://localhost:5274
```

```bash
python3 "Gabo AI/GaboAI.py" --serve --host 127.0.0.1 --port 8081
```

## Build

```bash
cd "The Triad PC"
dotnet build -c Release
```
