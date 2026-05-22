import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def load_dotenv_if_present(*paths: str) -> None:
    for p in paths:
        if not p:
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                for raw in f.readlines():
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and not os.environ.get(key):
                        os.environ[key] = value
        except FileNotFoundError:
            continue


def env_required(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Variabile d'ambiente mancante: {name}")
    return v


def env_optional(*names: str) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v and str(v).strip():
            return str(v).strip()
    return None


def slugify(value: str, max_len: int = 80) -> str:
    """
    Slug "URL-safe" (latinizzato) per link interni tipo /events/{slug}.
    Nota: non garantisce che l'app abbia già una pagina per quello slug:
    serve come identificatore stabile lato chat.
    """
    if not value:
        return "event"
    s = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    if not s:
        s = "event"
    return s[:max_len].strip("-")


def _ticketmaster_api_key() -> str | None:
    # Supporta naming diversi (repo .NET usa spesso TICKETMASTER_API_KEY).
    return env_optional(
        "TICKETMASTER_API_KEY",
        "TICKMASTER_API_CUSTOMER_KEY",  # presente in .envexample (typo storico)
        "TICKETMASTER_API_CUSTOMER_KEY",
        "TICKETMASTER_KEY",
    )


def _ticketmaster_base_url() -> str:
    return (os.environ.get("TICKETMASTER_BASE_URL") or "https://app.ticketmaster.com/discovery/v2/").rstrip("/") + "/"


def ticketmaster_search_events(keyword: str | None, city: str | None, size: int = 8) -> tuple[list[dict], str | None]:
    """
    Chiama Ticketmaster Discovery API e ritorna una lista "normalizzata" di eventi.
    Ritorna: (events, error_message)
    """
    api_key = _ticketmaster_api_key()
    if not api_key:
        return ([], None)  # opzionale: se manca, non blocchiamo la chat

    params: list[tuple[str, str]] = [
        ("apikey", api_key),
        ("locale", os.environ.get("TICKETMASTER_LOCALE") or "it"),
        ("countryCode", os.environ.get("TICKETMASTER_COUNTRY") or "IT"),
        ("sort", "date,asc"),
        ("size", str(max(1, min(int(size), 20)))),
    ]
    if keyword and keyword.strip():
        params.append(("keyword", keyword.strip()))
    if city and city.strip():
        params.append(("city", city.strip()))

    url = _ticketmaster_base_url() + "events.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        return ([], f"Errore Ticketmaster ({e.code}). {body}".strip())
    except Exception as e:
        return ([], f"Errore Ticketmaster. {str(e)}".strip())

    raw_events = (((data or {}).get("_embedded") or {}).get("events") or [])
    events: list[dict] = []
    for e in raw_events:
        try:
            event_id = e.get("id")
            name = e.get("name")
            url_tm = e.get("url")
            dates = e.get("dates") or {}
            start = dates.get("start") or {}
            local_date = start.get("localDate")
            local_time = start.get("localTime")

            venues = ((((e.get("_embedded") or {}).get("venues") or [])[:1]) or [{}])
            venue = venues[0] or {}
            venue_name = venue.get("name")
            city_name = ((venue.get("city") or {}).get("name")) or None
            country_code = ((venue.get("country") or {}).get("countryCode")) or None

            # Slug Ticketmaster: {slugified-name}--{event_id} (full id)
            # Esempio: "metallica-live--G5vYZb..." per poter ricostruire facilmente l'id.
            slug_base = slugify(str(name) if name else "event")
            slug = f"{slug_base}--{str(event_id)}" if event_id else slug_base

            events.append(
                {
                    "id": event_id,
                    "name": name,
                    "localDate": local_date,
                    "localTime": local_time,
                    "city": city_name,
                    "countryCode": country_code,
                    "venue": venue_name,
                    "ticketmasterUrl": url_tm,
                    "slug": slug,
                    "internalUrl": f"/events/{slug}",
                    "internalTicketmasterUrl": f"/events/tm/{event_id}" if event_id else None,
                    "source": "Ticketmaster Discovery API",
                }
            )
        except Exception:
            continue

    return (events, None)


def extract_prompt_and_history(req: dict) -> tuple[str | None, str | None, list[dict] | None]:
    """
    Supporta 2 contratti:
    - {prompt, system, history}
    - {messages:[{role,content}...]} (stile OpenAI/ChatFab)
    """
    prompt = req.get("prompt")
    system = req.get("system")
    history = req.get("history")

    if isinstance(prompt, str) and prompt.strip():
        return (prompt.strip(), system if isinstance(system, str) else None, history if isinstance(history, list) else None)

    messages = req.get("messages")
    if not isinstance(messages, list) or not messages:
        return (None, system if isinstance(system, str) else None, history if isinstance(history, list) else None)

    sys_parts: list[str] = []
    chat_history: list[dict] = []
    last_user: str | None = None

    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role == "system" and isinstance(content, str) and content.strip():
            sys_parts.append(content.strip())
            continue
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            chat_history.append({"role": role, "content": content.strip()})
            if role == "user":
                last_user = content.strip()

    # prompt = ultimo messaggio utente; history = precedente (esclude l'ultimo user)
    if last_user:
        # rimuove l'ultimo user dalla history per evitare duplicazione
        trimmed_history: list[dict] = []
        removed = False
        for m in reversed(chat_history):
            if not removed and m.get("role") == "user" and m.get("content") == last_user:
                removed = True
                continue
            trimmed_history.append(m)
        trimmed_history.reverse()
        merged_system = "\n\n".join(sys_parts) if sys_parts else None
        return (last_user, merged_system, trimmed_history if trimmed_history else None)

    merged_system = "\n\n".join(sys_parts) if sys_parts else None
    return (None, merged_system, chat_history if chat_history else None)


def infer_ticketmaster_filters(prompt: str) -> tuple[str | None, str | None]:
    """
    Estrae filtri minimi (keyword/city) dal prompt, senza fare NLP pesante.
    """
    p = (prompt or "").strip()
    if not p:
        return (None, None)

    cities = [
        "Milano",
        "Roma",
        "Bologna",
        "Torino",
        "Napoli",
        "Firenze",
        "Venezia",
        "Genova",
        "Bari",
        "Palermo",
        "Catania",
        "Verona",
        "Padova",
        "Parma",
        "Piacenza",
    ]
    city = None
    for c in cities:
        if re.search(rf"\b{re.escape(c)}\b", p, flags=re.IGNORECASE):
            city = c
            break

    keyword = None
    if len(p) <= 60:
        cleaned = p
        if city:
            cleaned = re.sub(rf"\b{re.escape(city)}\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.lower()
        cleaned = cleaned.replace("questa settimana", " ")
        cleaned = cleaned.replace("prossima settimana", " ")
        cleaned = cleaned.replace("settimana prossima", " ")
        cleaned = cleaned.replace("weekend", " ")
        cleaned = cleaned.replace("oggi", " ")
        cleaned = cleaned.replace("stasera", " ")
        cleaned = cleaned.replace("domani", " ")
        cleaned = cleaned.replace("eventi", " ")
        cleaned = cleaned.replace("evento", " ")
        cleaned = re.sub(r"[^\w\s]+", " ", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        keyword = cleaned if len(cleaned) >= 3 else None
    return (keyword, city)


def build_antihallucination_system(events: list[dict]) -> str:
    """
    Regole di comportamento + contesto "grounded" (eventi reali).
    """
    rules = [
        "Sei GaboAI, assistente eventi per The Triad PC Night Crew.",
        "Anti-hallucination: usa SOLO i dati presenti nel contesto 'EVENTI TICKETMASTER' qui sotto.",
        "Non inventare: date, orari, venue, città, prezzi, disponibilità, artisti, URL.",
        "Se l'utente chiede info non presenti nel contesto, rispondi chiaramente che non è verificabile dai dati disponibili e proponi di cercare con una keyword/città.",
        "Quando consigli un evento, includi sempre un link interno in formato /events/{slug} (campo internalUrl) e, se utile, anche il link Ticketmaster (ticketmasterUrl).",
        "Se non ci sono eventi in contesto, dillo e chiedi all'utente città/keyword.",
        "Formato consigliato: lista puntata con Nome, Data/Ora, Città, Venue, Link.",
    ]

    lines: list[str] = []
    lines.append("EVENTI TICKETMASTER (real-time, fonte: Ticketmaster Discovery API)")
    if not events:
        lines.append("- (nessun evento recuperato)")
    else:
        for e in events[:12]:
            name = e.get("name") or "Evento"
            local_date = e.get("localDate") or "Data da confermare"
            local_time = e.get("localTime") or ""
            dt = local_date if not local_time else f"{local_date} {local_time}"
            city = e.get("city") or "Città N/D"
            venue = e.get("venue") or "Venue N/D"
            internal_url = e.get("internalUrl") or ""
            tm_url = e.get("ticketmasterUrl") or ""
            lines.append(f"- {name} | {dt} | {city} | {venue} | internal: {internal_url} | ticketmaster: {tm_url}")

    return "\n".join(rules) + "\n\n" + "\n".join(lines)


def openrouter_chat(prompt: str, system: str | None, history: list[dict] | None, temperature: float, max_tokens: int) -> dict:
    api_key = env_required("OPENROUTER_API_KEY")
    base_url = os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    model = os.environ.get("OPENROUTER_MODEL") or "openai/gpt-4o-mini"

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        for m in history:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }

    url = base_url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        return {"reply": None, "model": None, "error": f"Errore OpenRouter ({e.code}). {body}".strip()}
    except Exception as e:
        return {"reply": None, "model": None, "error": f"Errore OpenRouter. {str(e)}".strip()}

    reply = None
    try:
        reply = data.get("choices", [{}])[0].get("message", {}).get("content")
    except Exception:
        reply = None

    if not reply or not isinstance(reply, str) or not reply.strip():
        return {"reply": None, "model": data.get("model"), "error": "Risposta vuota da OpenRouter."}

    return {"reply": reply, "model": data.get("model") or model, "error": None}

def build_fallback_reply(prompt: str, events: list[dict], tm_error: str | None, ai_error: str | None) -> str:
    if tm_error:
        return "In questo momento non riesco a recuperare gli eventi da Ticketmaster. Riprova tra poco o cambia città/keyword."
    if events:
        lines: list[str] = []
        lines.append("Ecco alcuni eventi trovati:")
        for e in events[:5]:
            name = e.get("name") or "Evento"
            local_date = e.get("localDate") or "Data da confermare"
            local_time = e.get("localTime") or ""
            dt = local_date if not local_time else f"{local_date} {local_time}"
            city = e.get("city") or "Città N/D"
            venue = e.get("venue") or "Venue N/D"
            internal_url = e.get("internalUrl") or ""
            tm_url = e.get("ticketmasterUrl") or ""
            link = internal_url if internal_url else tm_url
            lines.append(f"- {name} — {dt} — {city} — {venue} — {link}".strip())
        return "\n".join(lines)
    if ai_error:
        return "Al momento non riesco a generare la risposta. Riprova tra poco oppure scrivimi una città e una keyword (es. “Milano techno”)."
    return "Al momento non ho eventi disponibili nel contesto. Indicami la città o una keyword (es. “Milano techno”, “Roma jazz”) e controllo la disponibilità."


class Handler(BaseHTTPRequestHandler):
    server_version = "GaboAI/1.0"

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/chat":
            self._send_json(404, {"reply": None, "model": None, "error": "Not found"})
            return

        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"reply": None, "model": None, "error": "JSON non valido."})
            return

        prompt, system, history = extract_prompt_and_history(req if isinstance(req, dict) else {})
        temperature = (req.get("temperature", 0.2) if isinstance(req, dict) else 0.2)
        max_tokens = (req.get("max_tokens", 512) if isinstance(req, dict) else 512)

        if not isinstance(prompt, str) or not prompt.strip():
            self._send_json(400, {"reply": None, "model": None, "error": "Campo 'prompt' mancante."})
            return

        try:
            keyword, city = infer_ticketmaster_filters(prompt.strip())
            events, tm_error = ticketmaster_search_events(keyword=keyword, city=city, size=8)
            if not events and city and keyword:
                events2, tm_error2 = ticketmaster_search_events(keyword=None, city=city, size=8)
                if events2:
                    events = events2
                    tm_error = tm_error2

            anti = build_antihallucination_system(events)
            merged_system = anti if not system else (system.strip() + "\n\n" + anti)

            data = openrouter_chat(prompt.strip(), merged_system, history if isinstance(history, list) else None, temperature, max_tokens)

            reply = data.get("reply")
            ai_error = data.get("error")
            if not reply or not isinstance(reply, str) or not reply.strip():
                reply = build_fallback_reply(prompt.strip(), events, tm_error, ai_error)

            payload = {"reply": reply, "model": data.get("model"), "error": ai_error}
            payload["events"] = events
            if tm_error:
                payload["ticketmaster_error"] = tm_error
            self._send_json(200, payload)
        except Exception as e:
            self._send_json(500, {"reply": None, "model": None, "error": str(e)})

    def log_message(self, format: str, *args) -> None:
        return


def serve(host: str, port: int) -> None:
    httpd = HTTPServer((host, port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(prog="GaboAI")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    cwd = os.getcwd()
    script_dir = str(Path(__file__).resolve().parent)
    load_dotenv_if_present(os.path.join(cwd, ".env"), os.path.join(script_dir, ".env"), os.path.join(script_dir, "..", ".env"))

    if args.serve:
        missing = []
        for k in ("OPENROUTER_API_KEY",):
            if not os.environ.get(k):
                missing.append(k)
        if missing:
            sys.stderr.write("Variabili d'ambiente mancanti: " + ", ".join(missing) + "\n")
            return 2

        serve(args.host, args.port)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
