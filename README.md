# The Triad PC — Night Crew

Portale web in stile “dark tech / neon arancio” per scoprire eventi e contenuti editoriali, con chat “Gabo AI” (backend Python + OpenRouter).

## Clone

```bash
git clone https://github.com/<ORG>/<REPO>.git
cd The-Triad-PC-Night-Crew
```

## Requisiti

- .NET SDK 10
- Python 3

### Dipendenze Python

Il backend Python (Gabo AI) usa solo la standard library: il file `Gabo AI/requirements.txt` è volutamente vuoto.

Se vuoi mantenere il flusso “classico” con pip (anche se non installa nulla), puoi eseguire:

```bash
python3 -m pip install -r "Gabo AI/requirements.txt"
```

## Configurazione

Crea un file `.env` personale (non committarlo) partendo da `.envexample`:

```bash
cp .envexample .env
```

`.envexample` elenca tutte le variabili disponibili. Minimo consigliato per far funzionare tutto:

- `TICKETMASTER_API_KEY`: richiesto per vedere gli eventi Ticketmaster (API pubblica ma richiede ApiKey)
- `CHAT_API_URL`: richiesto per usare la chat dal portale (tipico locale: `http://127.0.0.1:8080/chat`)
- `OPENROUTER_API_KEY`: richiesto per far rispondere il backend chat Python

## Avvio in locale

Il portale .NET carica automaticamente un file `.env` se presente nella root/cwd. In alternativa puoi esportare le variabili nella shell prima di avviare.

```bash
set -a
source .env
set +a
```

### Avvia backend chat (Gabo AI)

```bash
python3 "Gabo AI/GaboAI.py" --serve --host 127.0.0.1 --port 8080
```

Healthcheck:

```bash
curl http://127.0.0.1:8080/health
```

Nota: per usare la chat dal portale, imposta `CHAT_API_URL` a `http://127.0.0.1:8080/chat`.

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

Publish (artefatto deploy):

```bash
dotnet publish -c Release -o ./out
```

## Deploy live (Blazor Server)

Esempio su Linux con systemd + Nginx (reverse proxy). La chat Python può girare sullo stesso host o su un host diverso: in entrambi i casi imposta `CHAT_API_URL` verso l’endpoint `/chat` del backend.

1) Pubblica l’app:

```bash
dotnet publish "The Triad PC/TheTriadPCNightCrew.csproj" -c Release -o /var/www/thetriadpc
```

2) Configura le variabili d’ambiente in produzione (consigliato: file separato non versionato):

- `/etc/thetriadpc/env` (esempio: vedi `.envexample`)
- Includi almeno `TICKETMASTER_API_KEY` e `CHAT_API_URL` (e, se serve, `CHAT_API_KEY`).

3) Crea un servizio systemd (indicativo):

```ini
# /etc/systemd/system/thetriadpc.service
[Unit]
Description=TheTriadPCNightCrew (Blazor Server)
After=network.target

[Service]
WorkingDirectory=/var/www/thetriadpc
ExecStart=/usr/bin/dotnet /var/www/thetriadpc/TheTriadPCNightCrew.dll
Environment=ASPNETCORE_ENVIRONMENT=Production
Environment=ASPNETCORE_URLS=http://127.0.0.1:5000
EnvironmentFile=/etc/thetriadpc/env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Attiva e avvia:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now thetriadpc
```

4) Nginx (WebSocket richiesti da Blazor Server):

```nginx
server {
  server_name example.com;

  location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

5) HTTPS: abilita TLS (es. Let’s Encrypt) e verifica che Nginx inoltri `X-Forwarded-*` correttamente.
