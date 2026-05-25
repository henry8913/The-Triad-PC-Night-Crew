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
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


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


def ticketmaster_search_events(
    keyword: str | None,
    city: str | None,
    size: int = 8,
    start_datetime_utc: str | None = None,
    end_datetime_utc: str | None = None,
) -> tuple[list[dict], str | None]:
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
    if start_datetime_utc and start_datetime_utc.strip():
        params.append(("startDateTime", start_datetime_utc.strip()))
    if end_datetime_utc and end_datetime_utc.strip():
        params.append(("endDateTime", end_datetime_utc.strip()))

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


def infer_when(prompt: str) -> str:
    p = (prompt or "").strip().lower()
    if not p:
        return "all"
    if "oggi" in p or "stasera" in p:
        return "today"
    if "weekend" in p:
        return "weekend"
    if "prossimi giorni" in p or "nei prossimi giorni" in p:
        return "this_week"
    if "questa settimana" in p:
        return "this_week"
    if "prossima settimana" in p or "settimana prossima" in p:
        return "next_week"
    return "all"


def build_date_range_utc_iso(when: str) -> tuple[str | None, str | None]:
    if when == "all":
        return (None, None)

    if ZoneInfo is None:
        return (None, None)

    tz = ZoneInfo("Europe/Rome")
    now = datetime.now(tz)
    today = now.date()

    if when == "today":
        start_local = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=tz)
        end_local = start_local + timedelta(days=1) - timedelta(seconds=1)
    elif when == "this_week":
        start_local = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=tz)
        end_local = start_local + timedelta(days=7) - timedelta(seconds=1)
    elif when == "next_week":
        start_local = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=tz) + timedelta(days=7)
        end_local = start_local + timedelta(days=7) - timedelta(seconds=1)
    elif when == "weekend":
        weekday = today.weekday()
        days_until_sat = (5 - weekday) % 7
        start_date = today + timedelta(days=days_until_sat)
        start_local = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=tz)
        end_local = start_local + timedelta(days=2) - timedelta(seconds=1)
    else:
        return (None, None)

    start_utc = start_local.astimezone(ZoneInfo("UTC"))
    end_utc = end_local.astimezone(ZoneInfo("UTC"))
    return (start_utc.isoformat().replace("+00:00", "Z"), end_utc.isoformat().replace("+00:00", "Z"))


def infer_limit(prompt: str) -> int:
    p = (prompt or "").lower()
    m = re.search(r"\b(\d{1,2})\b", p)
    if m:
        try:
            n = int(m.group(1))
            return max(1, min(n, 5))
        except Exception:
            pass
    if "qualche" in p or "alcuni" in p:
        return 4
    return 3


def build_compact_events_reply(events: list[dict], fallback_city: str | None) -> str:
    if not events:
        if fallback_city:
            return "Nessun evento trovato. Prova a cambiare keyword o città."
        return "Nessun evento trovato. Indicami una città o una keyword (es. “Milano techno”)."

    lines: list[str] = []
    for e in events:
        name = (e.get("name") or "Evento").strip()
        local_date = (e.get("localDate") or "").strip()
        local_time = (e.get("localTime") or "").strip()
        dt = local_date if not local_time else f"{local_date} {local_time}"
        venue = (e.get("venue") or "").strip()
        city = (e.get("city") or "").strip()
        internal_url = (e.get("internalUrl") or "").strip()

        parts = [name]
        if dt:
            parts.append(dt)
        if venue:
            parts.append(venue)
        if city:
            parts.append(city)
        if internal_url:
            parts.append(internal_url)
        lines.append(" • " + " — ".join(parts))

    return "\n".join(lines)


def is_event_intent(prompt: str) -> bool:
    p = (prompt or "").strip().lower()
    if not p:
        return False

    event_keywords = (
        "evento",
        "eventi",
        "festa",
        "feste",
        "serata",
        "serate",
        "concerto",
        "concerti",
        "live",
        "club",
        "party",
    )
    if any(k in p for k in event_keywords):
        return True

    _, city = infer_ticketmaster_filters(p)
    if city:
        return True

    time_keywords = (
        "stasera",
        "oggi",
        "weekend",
        "questa settimana",
        "prossima settimana",
        "settimana prossima",
    )
    prompt_keywords = (
        "cosa c'è",
        "che c'è",
        "cosa c’e",
        "che c’e",
        "cosa fare",
        "che faccio",
        "che si fa",
    )
    return any(k in p for k in prompt_keywords) and any(k in p for k in time_keywords)


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


def _extract_first_json_object(text: str) -> dict | None:
    if not text or not isinstance(text, str):
        return None
    s = text.strip()
    if not s:
        return None
    start = s.find("{")
    end = s.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return None
    candidate = s[start : end + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def get_brand_system_prompt() -> str:
    return "\n".join(
        [
            "Sei GaboAI, assistente ufficiale di The Triad PC — Night Crew.",
            "Tono: italiano, diretto, cyberpunk elegante, 'neon arancio, zero sbatti'.",
            "Contesto brand (dal sito):",
            "- Siamo nati a Piacenza (PC). Crew di amici e tecnologia al servizio della notte.",
            "- Problema: 'Che si fa stasera?' frammentato tra chat/storie/siti non aggiornati.",
            "- Missione: (1) Centralizzare locali e mood in un unico posto (2) Innovare con AI (3) Mappare l'Italia intera.",
            "- Per i locali: portiamo l'evento a chi cerca quel mood, senza algoritmi ciechi.",
            "Regole:",
            "- Risposte brevi e utili; fai 1 domanda di chiarimento solo se serve davvero.",
            "- Se l'utente chiede eventi, usa solo eventi reali (Ticketmaster) e rimanda ai link interni /events/{slug}.",
            "- Evita URL lunghi nel testo: se presenti eventi, l'interfaccia mostra già il pulsante LINK.",
            "- Consigli su serate/dating: generali e rispettosi; niente contenuti espliciti.",
        ]
    )


def openrouter_route_intent(prompt: str, history: list[dict] | None) -> dict | None:
    system = "\n".join(
        [
            "Decidi se l'utente sta chiedendo eventi o sta facendo conversazione/consigli generici.",
            "Rispondi SOLO con JSON, senza testo extra.",
            'Schema: {"intent":"chat"|"events","confidence":0..1,"city":string|null,"keyword":string|null,"when":"today"|"weekend"|"this_week"|"next_week"|"all","limit":1..5}.',
            "Regole:",
            "- intent=events solo se l'utente chiede esplicitamente eventi/serate/feste/concerto/live o 'cosa c'è stasera a X'.",
            "- Se è una domanda generica (es. 'cosa posso bere stasera?'), intent=chat.",
            "- when: deduci da oggi/stasera/weekend/questa settimana/prossima settimana, altrimenti all.",
            "- city: se presente (Milano, Roma, Bologna, Torino, Napoli, Firenze, Venezia, Genova, Bari, Palermo, Catania, Verona, Padova, Parma, Piacenza).",
            "- keyword: solo se c'è un mood/genre chiaro (es. techno, jazz).",
            "- limit: 3 default.",
            "- confidence: quanto sei sicuro della scelta intent (0=incerto, 1=molto sicuro).",
            "Esempi (usa questi come guida):",
            '- "feste a milano?" => intent=events, city="Milano"',
            '- "stasera a Roma che si fa?" => intent=events, city="Roma", when="today"',
            '- "cosa c’è questo weekend a Roma?" => intent=events, city="Roma", when="weekend"',
            '- "Milano questo weekend" => intent=events, city="Milano", when="weekend"',
            '- "Roma stasera" => intent=events, city="Roma", when="today"',
            '- "Bologna nei prossimi giorni" => intent=events, city="Bologna", when="this_week"',
            '- "Torino prossima settimana" => intent=events, city="Torino", when="next_week"',
            '- "eventi di oggi a Bologna" => intent=events, city="Bologna", when="today"',
            '- "concerti questa settimana a Torino" => intent=events, city="Torino", when="this_week"',
            '- "settimana prossima a Milano" => intent=events, city="Milano", when="next_week"',
            '- "techno a Milano sabato" => intent=events, city="Milano", keyword="techno", when="weekend"',
            '- "jazz a Roma" => intent=events, city="Roma", keyword="jazz"',
            '- "serata live a Piacenza" => intent=events, city="Piacenza", keyword="live"',
            '- "voglio qualcosa di tranquillo a Firenze" => intent=chat',
            '- "bar carino per primo appuntamento a Milano" => intent=chat',
            '- "dove porto una ragazza a Bologna?" => intent=chat',
            '- "dove andiamo con amici a Napoli?" => intent=chat',
            '- "consigliami una serata romantica" => intent=chat',
            '- "cosa mi metto per un concerto?" => intent=chat',
            '- "cosa posso bere stasera?" => intent=chat',
            '- "idee per pre-serata a casa" => intent=chat',
            '- "mi annoio, che faccio stasera?" => intent=chat',
            '- "che locali consigli in generale?" => intent=chat',
            '- "mi trovi 5 eventi a Milano?" => intent=events, city="Milano", limit=5',
            '- "dammi 2 eventi jazz a Roma" => intent=events, city="Roma", keyword="jazz", limit=2',
            '- "non ho la macchina, consigli?" => intent=chat',
            '- "zona Navigli cosa c’è stasera?" => intent=events, city="Milano", when="today"',
            '- "evento per portare una ragazza, qualcosa di elegante" => intent=chat',
            '- "cerco un after, roba techno" => intent=events, keyword="techno"',
        ]
    )
    data = openrouter_chat(prompt, system, history, temperature=0.0, max_tokens=180)
    reply = data.get("reply")
    if not isinstance(reply, str):
        return None
    parsed = _extract_first_json_object(reply)
    if not parsed:
        return None
    return parsed


def openrouter_select_event_ids(prompt: str, events: list[dict], limit: int) -> list[str]:
    if not events:
        return []
    compact = []
    for e in events[:12]:
        compact.append(
            {
                "id": e.get("id"),
                "name": e.get("name"),
                "city": e.get("city"),
                "venue": e.get("venue"),
                "localDate": e.get("localDate"),
                "localTime": e.get("localTime"),
                "internalUrl": e.get("internalUrl"),
            }
        )

    system = "\n".join(
        [
            "Seleziona i migliori eventi per la richiesta utente.",
            "Usa SOLO la lista EVENTI fornita, non inventare nulla.",
            "Rispondi SOLO con JSON: {\"ids\":[...]} con al massimo N id.",
            f"N={int(limit)}.",
            "Preferisci eventi coerenti con mood/keyword e città/periodo se citati.",
            "EVENTI:",
            json.dumps(compact, ensure_ascii=False),
        ]
    )
    data = openrouter_chat(prompt, system, history=None, temperature=0.0, max_tokens=220)
    reply = data.get("reply")
    if not isinstance(reply, str):
        return []
    parsed = _extract_first_json_object(reply)
    ids = parsed.get("ids") if isinstance(parsed, dict) else None
    if not isinstance(ids, list):
        return []
    out: list[str] = []
    for x in ids:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out[: int(limit)]


def openrouter_brief_message(user_prompt: str, facts: list[str], history: list[dict] | None) -> str | None:
    base = get_brand_system_prompt()
    extra = "\n".join(["Fatti (affidabili):"] + [f"- {x}" for x in facts])
    system = base + "\n\n" + extra + "\n\n" + "Rispondi in modo breve e chiaro (max 2 frasi). Non includere URL."
    data = openrouter_chat(user_prompt, system, history, temperature=0.2, max_tokens=120)
    reply = data.get("reply")
    return reply.strip() if isinstance(reply, str) and reply.strip() else None

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
            p = prompt.strip()
            if not os.environ.get("OPENROUTER_API_KEY"):
                self._send_json(
                    200,
                    {
                        "reply": "Configurazione mancante: imposta OPENROUTER_API_KEY e riprova.",
                        "model": None,
                        "error": "OPENROUTER_API_KEY mancante",
                        "events": [],
                    },
                )
                return

            if p.startswith("__NC_GREETING__"):
                p2 = p.replace("__NC_GREETING__", "", 1).strip()
                sys_prompt = get_brand_system_prompt() + "\n\n" + "\n".join(
                    [
                        "Obiettivo: scrivi un messaggio di benvenuto (mini presentazione).",
                        "Vincoli:",
                        "- max 2 frasi + 1 domanda finale (in totale max 3 frasi).",
                        "- spiega che sei GaboAI e che puoi: (1) dare consigli su serate/locali/mood (2) trovare eventi reali e aprirli con LINK.",
                        "- usa tono Night Crew: neon arancio, zero sbatti.",
                        "- includi un esempio semplice tra virgolette con città e tempo (es. “Milano questo weekend”). Mood opzionale.",
                        f"Contesto pagina: {p2}",
                    ]
                )
                data = openrouter_chat(p2 or "Benvenuto", sys_prompt, history if isinstance(history, list) else None, temperature=0.2, max_tokens=140)
                reply = data.get("reply")
                if not isinstance(reply, str) or not reply.strip():
                    reply = "Sono GaboAI di Night Crew: ti aiuto a scegliere serate e a trovare eventi reali, zero sbatti. Dimmi città e quando (es. “Milano questo weekend”) oppure chiedimi un consiglio per stasera."
                self._send_json(200, {"reply": reply.strip(), "model": data.get("model"), "error": data.get("error"), "events": []})
                return

            router = openrouter_route_intent(p, history if isinstance(history, list) else None)
            router_intent = router.get("intent") if isinstance(router, dict) else None
            router_conf = router.get("confidence") if isinstance(router, dict) else None
            try:
                router_conf_f = float(router_conf) if router_conf is not None else 0.0
            except Exception:
                router_conf_f = 0.0
            router_conf_f = max(0.0, min(1.0, router_conf_f))

            intent = router_intent if router_intent in ("chat", "events") else None
            if intent is None:
                intent = "events" if is_event_intent(p) else "chat"
            elif router_conf_f < 0.55:
                heuristic_events = is_event_intent(p)
                if intent == "events" and not heuristic_events:
                    intent = "chat"
                elif intent == "chat" and heuristic_events:
                    intent = "events"

            if intent == "events":
                if not _ticketmaster_api_key():
                    reply = openrouter_brief_message(
                        p,
                        ["Ticketmaster non è configurato sul server.", "Serve TICKETMASTER_API_KEY per cercare eventi pubblici."],
                        history if isinstance(history, list) else None,
                    ) or "Per consigliarti eventi devo avere Ticketmaster configurato. Imposta TICKETMASTER_API_KEY e riprova."
                    self._send_json(200, {"reply": reply, "model": None, "error": "TICKETMASTER_API_KEY mancante", "events": []})
                    return

                keyword = (router.get("keyword") if isinstance(router, dict) else None) if isinstance(router, dict) else None
                city = (router.get("city") if isinstance(router, dict) else None) if isinstance(router, dict) else None
                when = (router.get("when") if isinstance(router, dict) else None) if isinstance(router, dict) else None
                limit = (router.get("limit") if isinstance(router, dict) else None) if isinstance(router, dict) else None

                if not isinstance(keyword, str):
                    keyword = None
                if keyword:
                    keyword = keyword.strip() or None
                if not isinstance(city, str):
                    city = None
                if city:
                    city = city.strip() or None
                if not isinstance(when, str) or when not in ("today", "weekend", "this_week", "next_week", "all"):
                    when = infer_when(p)
                try:
                    limit = int(limit) if limit is not None else infer_limit(p)
                except Exception:
                    limit = infer_limit(p)
                limit = max(1, min(int(limit), 5))

                if not city and not keyword:
                    if router_conf_f >= 0.65:
                        facts = [
                            "Per cercare eventi mi serve almeno una città e un periodo (oggi, weekend, prossimi giorni).",
                            "Esempi: “Milano questo weekend”, “Roma stasera”, “Bologna nei prossimi giorni”.",
                        ]
                        fallback = "Dimmi una città e quando (es. “Milano questo weekend”) e ti propongo 3 eventi."
                    else:
                        facts = [
                            "Posso darti consigli (serata, locali, vibe) oppure cercare eventi reali.",
                            "Se vuoi eventi, dimmi almeno città e quando (es. “Milano questo weekend”).",
                        ]
                        fallback = "Vuoi un consiglio generale o vuoi che ti trovi eventi reali? Se vuoi eventi dimmi città e quando (es. “Milano questo weekend”)."

                    reply = openrouter_brief_message(p, facts, history if isinstance(history, list) else None) or fallback
                    self._send_json(200, {"reply": reply, "model": None, "error": None, "events": []})
                    return

                start_utc, end_utc = build_date_range_utc_iso(when)
                events, tm_error = ticketmaster_search_events(
                    keyword=keyword,
                    city=city,
                    size=20,
                    start_datetime_utc=start_utc,
                    end_datetime_utc=end_utc,
                )

                if not events and city and keyword:
                    events2, tm_error2 = ticketmaster_search_events(
                        keyword=None,
                        city=city,
                        size=20,
                        start_datetime_utc=start_utc,
                        end_datetime_utc=end_utc,
                    )
                    if events2:
                        events = events2
                        tm_error = tm_error2

                if tm_error:
                    reply = openrouter_brief_message(
                        p,
                        ["Il servizio Ticketmaster ha risposto con un errore temporaneo.", "Puoi riprovare tra poco o cambiare città/keyword."],
                        history if isinstance(history, list) else None,
                    ) or "Non riesco a recuperare gli eventi in questo momento. Riprova tra poco."
                    self._send_json(200, {"reply": reply, "model": None, "error": tm_error, "events": []})
                    return

                if not events:
                    reply = openrouter_brief_message(
                        p,
                        ["Nessun evento trovato con i filtri attuali."],
                        history if isinstance(history, list) else None,
                    ) or "Nessun evento trovato. Prova a cambiare keyword o città."
                    self._send_json(200, {"reply": reply, "model": None, "error": None, "events": []})
                    return

                ids = openrouter_select_event_ids(p, events, limit)
                chosen = [e for e in events if e.get("id") in set(ids)] if ids else events[:limit]
                if len(chosen) > limit:
                    chosen = chosen[:limit]

                base = get_brand_system_prompt()
                anti = build_antihallucination_system(chosen)
                merged_system = base + "\n\n" + anti
                data = openrouter_chat(
                    p,
                    merged_system,
                    history if isinstance(history, list) else None,
                    temperature=0.2,
                    max_tokens=180,
                )
                reply = data.get("reply")
                if not isinstance(reply, str) or not reply.strip():
                    reply = openrouter_brief_message(
                        p,
                        [f"Ho trovato {len(chosen)} eventi reali coerenti con la richiesta."],
                        history if isinstance(history, list) else None,
                    ) or f"Ecco {len(chosen)} proposte. Clicca LINK per aprire l’evento."
                self._send_json(200, {"reply": reply.strip(), "model": data.get("model"), "error": data.get("error"), "events": chosen})
                return

            base = get_brand_system_prompt()
            merged_system = base if not system else (system.strip() + "\n\n" + base)
            data = openrouter_chat(p, merged_system, history if isinstance(history, list) else None, temperature, max_tokens)

            reply = data.get("reply")
            ai_error = data.get("error")
            if not isinstance(reply, str) or not reply.strip():
                reply = "Dimmi cosa cerchi (mood, città, con chi esci) e ti do un consiglio zero sbatti."

            self._send_json(200, {"reply": reply.strip(), "model": data.get("model"), "error": ai_error, "events": []})
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
        if not os.environ.get("OPENROUTER_API_KEY"):
            missing.append("OPENROUTER_API_KEY")
        if not _ticketmaster_api_key():
            missing.append("TICKETMASTER_API_KEY")
        if missing:
            sys.stderr.write("Variabili d'ambiente mancanti: " + ", ".join(missing) + "\n")
            return 2

        serve(args.host, args.port)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
