"""
Hisense IR Remote — FastAPI control server.

Endpoints (user-facing, require Google JWT):
  GET  /                         → serve web GUI
  GET  /api/buttons              → list all Hisense button definitions
  POST /api/command/button/{name}→ queue a named Hisense button press
  POST /api/command/raw          → queue a raw NEC/RC5/Sony command
  GET  /api/status               → queue length + last 20 history entries
  GET  /auth/login               → start Google OAuth2 flow
  GET  /auth/callback            → Google OAuth2 callback → issues JWT

Endpoints (Pico device, require PICO_DEVICE_TOKEN):
  GET  /api/next-command         → dequeue next pending command (or null)
  POST /api/ack/{cmd_id}         → mark command as transmitted

Configuration via .env (see .env.example):
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY, PICO_DEVICE_TOKEN
"""

import os
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from jose import JWTError, jwt

from hisense_codes import all_buttons, get_command

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

_GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
_GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
_SECRET_KEY           = os.getenv("SECRET_KEY", "change-me-in-production")
_PICO_DEVICE_TOKEN    = os.getenv("PICO_DEVICE_TOKEN", "change-me-pico-token")
_JWT_ALGORITHM        = "HS256"
_JWT_EXPIRE_DAYS      = 30

# ── App + middleware ───────────────────────────────────────────────────────────

app = FastAPI(title="Hisense IR Remote Server")
app.add_middleware(SessionMiddleware, secret_key=_SECRET_KEY)

# ── Google OAuth2 ─────────────────────────────────────────────────────────────

oauth = OAuth()
oauth.register(
    name="google",
    client_id=_GOOGLE_CLIENT_ID,
    client_secret=_GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ── In-memory state ───────────────────────────────────────────────────────────

_queue:   deque[dict]   = deque()
_history: dict[str, dict] = {}

# ── JWT helpers ───────────────────────────────────────────────────────────────

def _create_jwt(email: str) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": email,
        "iat": now,
        "exp": now + timedelta(days=_JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_JWT_ALGORITHM)


def _decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

# ── Auth dependencies ─────────────────────────────────────────────────────────

def _require_user(request: Request) -> dict:
    """Dependency: validates Google-issued JWT from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return _decode_jwt(auth[7:])


def _require_pico(request: Request) -> bool:
    """Dependency: validates static Pico device token."""
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {_PICO_DEVICE_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid device token")
    return True

# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/auth/login")
async def auth_login(request: Request):
    """Redirect the browser to Google's OAuth2 consent page."""
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, str(redirect_uri))


@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    """Google redirects here after consent.  Issue a 30-day JWT and send it to
    the SPA via a URL fragment so JavaScript can store it without a round-trip."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OAuth error: {exc}") from exc

    user_info = token.get("userinfo") or {}
    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="No email in Google profile")

    jwt_token = _create_jwt(email)
    # Pass token to SPA via fragment — never lands in server logs or Referer headers
    return RedirectResponse(url=f"/#token={jwt_token}")

# ── User API ──────────────────────────────────────────────────────────────────

@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/api/buttons")
async def list_buttons(_user: dict = Depends(_require_user)):
    """Return all Hisense button definitions."""
    return all_buttons()


@app.post("/api/command/button/{name}", status_code=202)
async def send_button(name: str, _user: dict = Depends(_require_user)):
    """Queue a named Hisense button press."""
    cmd_def = get_command(name)
    if cmd_def is None:
        raise HTTPException(status_code=404, detail=f"Unknown button: '{name}'")

    cmd_id = str(uuid.uuid4())
    cmd = {
        "id":       cmd_id,
        "status":   "queued",
        "queued_by": _user["sub"],
        **cmd_def,
    }
    _queue.append(cmd)
    _history[cmd_id] = cmd
    return {"id": cmd_id, "status": "queued"}


@app.post("/api/command/raw", status_code=202)
async def send_raw(request: Request, _user: dict = Depends(_require_user)):
    """Queue a raw IR command (any protocol).

    Body:  { "protocol": "nec"|"rc5"|"sony",
             "address": int, "command": int,    # NEC / RC5
             "data": int, "bits": int,           # Sony
             "repeats": int }
    """
    body = await request.json()
    if "protocol" not in body:
        raise HTTPException(status_code=422, detail="'protocol' field required")

    cmd_id = str(uuid.uuid4())
    cmd = {
        "id":        cmd_id,
        "status":    "queued",
        "queued_by": _user["sub"],
        **body,
    }
    _queue.append(cmd)
    _history[cmd_id] = cmd
    return {"id": cmd_id, "status": "queued"}


@app.get("/api/status")
async def queue_status(_user: dict = Depends(_require_user)):
    return {
        "queued":  len(_queue),
        "history": list(_history.values())[-20:],
    }

# ── Pico device API ───────────────────────────────────────────────────────────

@app.get("/api/next-command")
async def next_command(_auth: bool = Depends(_require_pico)):
    """Dequeue and return the next pending command, or null if the queue is empty."""
    if _queue:
        cmd = _queue.popleft()
        cmd["status"] = "sent"
        return JSONResponse(content=cmd)
    return JSONResponse(content=None)


@app.post("/api/ack/{cmd_id}")
async def ack_command(cmd_id: str, request: Request, _auth: bool = Depends(_require_pico)):
    """Mark a command as transmitted by the Pico."""
    body = await request.json()
    if cmd_id in _history:
        _history[cmd_id]["status"] = body.get("status", "transmitted")
    return {"ok": True}

# ── Static / SPA ──────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_gui():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html")) as fh:
        return HTMLResponse(fh.read())
