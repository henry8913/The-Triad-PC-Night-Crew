import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


def _find_upwards(start_dir: str, filename: str, max_depth: int = 6) -> Optional[str]:
    try:
        current = os.path.abspath(start_dir)
        for _ in range(max(1, max_depth)):
            candidate = os.path.join(current, filename)
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
    except Exception:
        return None
    return None


def load_dotenv_if_present(filename: str = ".env") -> int:
    path = _find_upwards(os.getcwd(), filename, max_depth=6)
    if not path:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if not os.path.isfile(path):
            path = _find_upwards(os.path.dirname(os.path.abspath(__file__)), filename, max_depth=6)
    if not path or not os.path.isfile(path):
        return 0

    count = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].lstrip()
                if "=" not in line:
                    continue
                key, value_part = line.split("=", 1)
                key = key.strip()
                if not key:
                    continue
                if os.environ.get(key):
                    continue
                value = _parse_dotenv_value(value_part.strip())
                os.environ[key] = value
                count += 1
    except Exception:
        return 0

    return count


def _parse_dotenv_value(value_part: str) -> str:
    if not value_part:
        return ""
    if (value_part.startswith('"') and value_part.endswith('"')) or (value_part.startswith("'") and value_part.endswith("'")):
        quote = value_part[0]
        inner = value_part[1:-1]
        return _unescape_double_quoted(inner) if quote == '"' else inner
    cut = _index_of_inline_comment_start(value_part)
    if cut >= 0:
        value_part = value_part[:cut].rstrip()
    return value_part


def _index_of_inline_comment_start(value_part: str) -> int:
    for i, ch in enumerate(value_part):
        if ch != "#":
            continue
        if i == 0 or value_part[i - 1].isspace():
            return i
    return -1


def _unescape_double_quoted(s: str) -> str:
    return (
        s.replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _read_json_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    body = handler.rfile.read(length)
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return {}


def _now_rome() -> datetime:
    if ZoneInfo is None:
        return datetime.now(timezone.utc)
    return datetime.now(ZoneInfo("Europe/Rome"))


def _to_utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class TimeRange:
    start_utc_z: str
    end_utc_z: str
    label: str


ITALIAN_CITIES = {
    "milano",
    "roma",
    "bologna",
    "torino",
    "napoli",
    "firenze",
    "venezia",
    "genova",
    "palermo",
    "catania",
    "bari",
    "verona",
    "padova",
    "trieste",
    "bergamo",
    "brescia",
    "parma",
    "modena",
    "reggio emilia",
    "ravenna",
    "rimini",
    "pisa",
    "livorno",
    "lecce",
    "salerno",
    "perugia",
    "ancona",
    "pescara",
    "udine",
    "trento",
    "bolzano",
    "aosta",
    "cagliari",
    "sassari",
    "como",
    "novara",
    "monza",
    "vicenza",
    "treviso",
    "cesena",
    "ferrara",
    "latina",
    "frosinone",
    "taranto",
    "brindisi",
    "siracusa",
    "messina",
}


def _normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def extract_city_from_text(text: str) -> Optional[str]:
    t = _normalize_spaces(text).lower()
    if not t:
        return None

    for city in sorted(ITALIAN_CITIES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(city)}\b", t):
            return city.title()

    m = re.search(r"\b(?:a|ad|in)\s+([a-zà-öø-ÿ'’\- ]{2,})\b", t, flags=re.IGNORECASE)
    if m:
        candidate = _normalize_spaces(m.group(1))
        candidate = re.split(r"\b(?:stasera|oggi|domani|weekend|questa settimana|questo weekend)\b", candidate, 1)[0].strip()
        candidate = re.split(r"[,\.\!\?]", candidate, 1)[0].strip()
        if 2 <= len(candidate) <= 40:
            return candidate.title()

    if re.fullmatch(r"[a-zà-öø-ÿ'’\-]{2,}", t, flags=re.IGNORECASE):
        return t.title()

    return None


def extract_time_range_from_text(text: str, now_local: datetime) -> Optional[TimeRange]:
    t = _normalize_spaces(text).lower()
    if not t:
        return None

    def day_range(day_local: datetime, label: str) -> TimeRange:
        start = day_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end = day_local.replace(hour=23, minute=59, second=59, microsecond=0)
        return TimeRange(_to_utc_z(start), _to_utc_z(end), label)

    if "stasera" in t or "tonight" in t:
        start = now_local.replace(microsecond=0)
        end = now_local.replace(hour=23, minute=59, second=59, microsecond=0)
        return TimeRange(_to_utc_z(start), _to_utc_z(end), "stasera")

    if "oggi" in t:
        return day_range(now_local, "oggi")

    if "domani" in t:
        return day_range(now_local + timedelta(days=1), "domani")

    if "questa settimana" in t or "this week" in t or "settimana" in t:
        start = now_local.replace(microsecond=0)
        end = (now_local + timedelta(days=7)).replace(microsecond=0)
        return TimeRange(_to_utc_z(start), _to_utc_z(end), "nei prossimi 7 giorni")

    if "weekend" in t:
        weekday = now_local.weekday()  # Mon=0 ... Sun=6
        if weekday <= 4:
            days_to_sat = 5 - weekday
        else:
            days_to_sat = 0 if weekday == 5 else -1
        sat = (now_local + timedelta(days=days_to_sat)).replace(hour=0, minute=0, second=0, microsecond=0)
        sun = (sat + timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
        return TimeRange(_to_utc_z(sat), _to_utc_z(sun), "questo weekend")

    m = re.search(r"\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?\b", t)
    if m:
        dd = int(m.group(1))
        mm = int(m.group(2))
        yy_raw = m.group(3)
        if yy_raw:
            yy = int(yy_raw)
            if yy < 100:
                yy += 2000
        else:
            yy = now_local.year
        try:
            if ZoneInfo is None:
                dt = datetime(yy, mm, dd, tzinfo=timezone.utc)
            else:
                dt = datetime(yy, mm, dd, tzinfo=now_local.tzinfo)
            return day_range(dt, f"{dd:02d}/{mm:02d}")
        except Exception:
            return None

    return None


def looks_like_event_intent(text: str) -> bool:
    t = _normalize_spaces(text).lower()
    if not t:
        return False
    intent_words = [
        "eventi",
        "evento",
        "cosa c'è",
        "cosa ce",
        "cosa c’e",
        "after",
        "afterparty",
        "party",
        "serata",
        "club",
        "concerto",
        "live",
        "dj",
        "festival",
    ]
    if any(w in t for w in intent_words):
        return True
    city = extract_city_from_text(text)
    when = extract_time_range_from_text(text, _now_rome())
    if city and when:
        return True
    return False


def extract_keyword(text: str) -> Optional[str]:
    t = _normalize_spaces(text).lower()
    if not t:
        return None
    if "afterparty" in t or re.search(r"\bafter\b", t):
        return "after"
    for k in ["techno", "house", "rap", "trap", "reggaeton", "latin", "commerciale", "indie", "rock", "metal", "jazz"]:
        if re.search(rf"\b{re.escape(k)}\b", t):
            return k
    return None


def _collect_last_user_text(messages: List[Dict[str, Any]]) -> str:
    for m in reversed(messages):
        if (m.get("role") or "").lower() == "user":
            return str(m.get("content") or "")
    return ""


def _extract_slots(messages: List[Dict[str, Any]]) -> Tuple[Optional[str], TimeRange, Optional[str], str]:
    now_local = _now_rome()
    last_user = _collect_last_user_text(messages)

    city = None
    when = None
    keyword = None

    for m in reversed(messages[-10:]):
        if (m.get("role") or "").lower() != "user":
            continue
        content = str(m.get("content") or "")
        if city is None:
            city = extract_city_from_text(content)
        if when is None:
            when = extract_time_range_from_text(content, now_local)
        if keyword is None:
            keyword = extract_keyword(content)
        if city and when and keyword:
            break

    if when is None:
        start = now_local.replace(microsecond=0)
        end = (now_local + timedelta(days=7)).replace(microsecond=0)
        when = TimeRange(_to_utc_z(start), _to_utc_z(end), "nei prossimi 7 giorni")

    return city, when, keyword, last_user


def ticketmaster_search_events(
    *,
    city: str,
    when: TimeRange,
    keyword: Optional[str],
    size: int,
    cfg: Dict[str, str],
    timeout_s: int = 10,
) -> List[Dict[str, Any]]:
    api_key = cfg.get("TICKETMASTER_API_KEY") or ""
    if not api_key.strip():
        raise RuntimeError("TICKETMASTER_API_KEY mancante")

    base_url = (cfg.get("TICKETMASTER_BASE_URL") or "https://app.ticketmaster.com/discovery/v2/").rstrip("/") + "/"
    locale = (cfg.get("TICKETMASTER_LOCALE") or "it").strip()
    country = (cfg.get("TICKETMASTER_COUNTRY") or "IT").strip()

    params = {
        "apikey": api_key,
        "locale": locale,
        "countryCode": country,
        "city": city,
        "sort": "date,asc",
        "size": str(max(1, min(20, size))),
        "page": "0",
        "startDateTime": when.start_utc_z,
        "endDateTime": when.end_utc_z,
    }
    if keyword:
        params["keyword"] = keyword

    url = base_url + "events.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as ex:
        if ex.code == 401 or ex.code == 403:
            raise RuntimeError("ApiKey Ticketmaster non valida")
        if ex.code == 429:
            raise RuntimeError("Rate limit Ticketmaster. Riprova tra poco.")
        raise RuntimeError(f"Errore Ticketmaster (HTTP {ex.code})")
    except urllib.error.URLError:
        raise RuntimeError("Ticketmaster non raggiungibile")
    except Exception:
        raise RuntimeError("Errore leggendo Ticketmaster")

    events = (((data or {}).get("_embedded") or {}).get("events") or []) if isinstance(data, dict) else []
    out: List[Dict[str, Any]] = []
    for e in events:
        if not isinstance(e, dict):
            continue
        eid = str(e.get("id") or "").strip()
        name = str(e.get("name") or "").strip()
        if not eid or not name:
            continue
        dates = (e.get("dates") or {}).get("start") or {}
        local_date = dates.get("localDate")
        local_time = dates.get("localTime")
        venues = (((e.get("_embedded") or {}).get("venues")) or [])
        venue_name = None
        if venues and isinstance(venues[0], dict):
            venue_name = venues[0].get("name")
        out.append(
            {
                "id": eid,
                "name": name,
                "venue": venue_name,
                "localDate": local_date,
                "localTime": local_time,
                "internalUrl": f"/events/tm/{urllib.parse.quote(eid)}",
            }
        )
    return out


def build_events_reply(city: str, when: TimeRange, keyword: Optional[str], events: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not events:
        return {"reply": "Nessun evento trovato, prova a cambiare quando o città.", "events": []}

    picked = events[:3]
    tag = f" per {keyword}" if keyword else ""
    reply = f"In {city} {when.label}{tag}: te ne lascio 3, clicca e vai."
    return {
        "reply": reply,
        "events": [
            {
                "name": e.get("name"),
                "venue": e.get("venue"),
                "localDate": e.get("localDate"),
                "localTime": e.get("localTime"),
                "internalUrl": e.get("internalUrl"),
            }
            for e in picked
        ],
    }


def _openrouter_chat(messages: List[Dict[str, str]], cfg: Dict[str, str], timeout_s: int = 20) -> str:
    api_key = cfg.get("OPENROUTER_API_KEY") or ""
    if not api_key.strip():
        raise RuntimeError("OPENROUTER_API_KEY mancante")

    base_url = (cfg.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
    model = (cfg.get("OPENROUTER_MODEL") or "openai/gpt-4o-mini").strip()

    url = base_url + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": 220,
    }
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=raw, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError as ex:
        try:
            detail = ex.read().decode("utf-8")
        except Exception:
            detail = ""
        raise RuntimeError(f"OpenRouter error (HTTP {ex.code}) {detail}".strip())
    except urllib.error.URLError:
        raise RuntimeError("OpenRouter non raggiungibile")
    except Exception:
        raise RuntimeError("Errore chiamando OpenRouter")

    try:
        choices = data.get("choices") or []
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    except Exception:
        pass

    raise RuntimeError("Risposta OpenRouter vuota")


SYSTEM_PROMPT = """Sei Gabo AI, buttafuori digitale e coach della serata per Night Crew.
Tono: breve, diretto, zero sbatti. Italiano naturale da notte.
Regole:
- Non inventare eventi, nomi di locali o link. Se l'utente chiede eventi, sarà un altro modulo a fornirli.
- Se mancano info, fai al massimo 1 domanda secca.
- Rispondi in 1-2 frasi, massimo 3 se serve. Niente liste lunghe."""


def coach_reply(messages: List[Dict[str, Any]], cfg: Dict[str, str]) -> Dict[str, Any]:
    chat_messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in messages[-10:]:
        role = (m.get("role") or "").lower()
        content = str(m.get("content") or "")
        if role not in {"user", "assistant"}:
            continue
        if not content.strip():
            continue
        chat_messages.append({"role": role, "content": content})

    try:
        text = _openrouter_chat(chat_messages, cfg)
        text = text.strip()
        if len(text) > 650:
            text = text[:650].rstrip() + "…"
        return {"reply": text, "events": []}
    except Exception:
        last_user = _collect_last_user_text(messages)
        fallback = "Dimmi città + quando (stasera/weekend) e ti sparo 3 idee vere."
        if any(w in _normalize_spaces(last_user).lower() for w in ["piove", "freddo", "caldo", "macchina", "ragazza", "tranquillo"]):
            fallback = "Ok. Dimmi solo città + quando e ti trovo 3 opzioni easy (zero sbatti)."
        return {"reply": fallback, "events": []}


def greeting_reply(path: str) -> Dict[str, Any]:
    p = (path or "").strip()
    if p.startswith("/events"):
        return {"reply": "Yo. Dimmi: città + quando (stasera/weekend). Ti porto su 3 eventi veri.", "events": []}
    if p.startswith("/cities"):
        return {"reply": "Scegli la città e fammi capire quando: stasera o weekend?", "events": []}
    return {"reply": "Yo, Night Crew. Che vibe vuoi stasera? (tranquillo / club / after)", "events": []}


def _is_city_only(text: str) -> bool:
    city = extract_city_from_text(text or "")
    if not city:
        return False
    t = re.sub(r"[^\wà-öø-ÿ'’\- ]+", " ", (text or "").lower())
    t = _normalize_spaces(t)
    return t == city.lower()


def _is_time_only(text: str) -> bool:
    now_local = _now_rome()
    tr = extract_time_range_from_text(text or "", now_local)
    if not tr:
        return False
    t = _normalize_spaces((text or "").lower())
    if re.fullmatch(r"(stasera|oggi|domani|questo weekend|weekend|questa settimana|nei prossimi 7 giorni)", t):
        return True
    if re.fullmatch(r"\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?", t):
        return True
    return False


def route_chat(payload: Dict[str, Any], cfg: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    if isinstance(payload.get("prompt"), str):
        prompt = payload.get("prompt") or ""
        if prompt.startswith("__NC_GREETING__"):
            path = prompt[len("__NC_GREETING__") :].strip()
            return 200, greeting_reply(path)
        messages = [{"role": "user", "content": prompt}]
    else:
        messages = payload.get("messages") or []
        if not isinstance(messages, list):
            messages = []

    last_user = _collect_last_user_text(messages)
    if not last_user.strip():
        return 200, {"reply": "Dimmi cosa vuoi fare stasera.", "events": []}

    event_mode = looks_like_event_intent(last_user)
    if not event_mode and (_is_city_only(last_user) or _is_time_only(last_user)):
        for m in reversed(messages[-10:-1]):
            role = (m.get("role") or "").lower()
            content = str(m.get("content") or "")
            if role == "user" and looks_like_event_intent(content):
                event_mode = True
                break
            if role == "assistant" and any(x in _normalize_spaces(content).lower() for x in ["che città", "quando", "stasera", "weekend"]):
                event_mode = True
                break

    if event_mode:
        city, when, keyword, _ = _extract_slots(messages)
        if not city:
            return 200, {"reply": "Che città?", "events": []}
        try:
            evs = ticketmaster_search_events(city=city, when=when, keyword=keyword, size=5, cfg=cfg)
            return 200, build_events_reply(city, when, keyword, evs)
        except RuntimeError as ex:
            msg = str(ex)
            if "mancante" in msg.lower():
                return 200, {"reply": "Ticketmaster non è configurato. Metti TICKETMASTER_API_KEY nel .env.", "events": []}
            return 200, {"reply": "Nessun evento trovato, prova a cambiare quando o città.", "events": []}

    return 200, coach_reply(messages, cfg)


class Handler(BaseHTTPRequestHandler):
    server_version = "GaboAI/1.0"

    def do_GET(self) -> None:
        if self.path.startswith("/health"):
            _json_response(self, 200, {"ok": True, "ts": int(time.time())})
            return
        _json_response(self, 404, {"error": "not_found"})

    def do_POST(self) -> None:
        if not self.path.startswith("/chat"):
            _json_response(self, 404, {"error": "not_found"})
            return
        payload = _read_json_body(self)
        code, body = route_chat(payload, self.server.cfg)  # type: ignore[attr-defined]
        _json_response(self, code, body)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def serve(host: str, port: int) -> None:
    load_dotenv_if_present()
    cfg = dict(os.environ)
    httpd = HTTPServer((host, port), Handler)
    httpd.cfg = cfg  # type: ignore[attr-defined]
    print(f"Gabo AI listening on http://{host}:{port}", file=sys.stderr)
    httpd.serve_forever()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="GaboAI")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)

    if args.serve:
        serve(args.host, args.port)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
