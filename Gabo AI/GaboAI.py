import argparse
import json
import os
import sys
import time
import urllib.error
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

        prompt = req.get("prompt")
        system = req.get("system")
        history = req.get("history")
        temperature = req.get("temperature", 0.2)
        max_tokens = req.get("max_tokens", 512)

        if not isinstance(prompt, str) or not prompt.strip():
            self._send_json(400, {"reply": None, "model": None, "error": "Campo 'prompt' mancante."})
            return

        try:
            data = openrouter_chat(prompt.strip(), system if isinstance(system, str) else None, history if isinstance(history, list) else None, temperature, max_tokens)
            self._send_json(200, {"reply": data.get("reply"), "model": data.get("model"), "error": data.get("error")})
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
