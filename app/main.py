import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    COOKIE_SECURE,
    USES_DEFAULT_SECRETS,
    check_password,
    create_session_token,
    is_login_rate_limited,
    is_valid_session_token,
    record_failed_login,
    reset_login_attempts,
)
from app.db import get_session, init_db
from app.models import Game, TimerState
from app.ws import manager

logger = logging.getLogger("winchallenge")

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Win Challenge")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Pfade, die ohne gÃ¼ltige Session erreichbar sein mÃ¼ssen
PUBLIC_PATHS = {"/login", "/favicon.ico"}


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    if USES_DEFAULT_SECRETS:
        logger.warning(
            "APP_PASSWORD und/oder SECRET_KEY verwenden noch den Standardwert! "
            "Vor der Veroeffentlichung unbedingt in der .env bzw. den Umgebungsvariablen aendern."
        )


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/static") or path in PUBLIC_PATHS:
        return await call_next(request)
    if not is_valid_session_token(request.cookies.get(COOKIE_NAME)):
        return RedirectResponse(url="/login")
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})


@app.head("/login")
def login_page_head() -> Response:
    # Uptime-Monitore (z.B. UptimeRobot Free) pingen /login per HEAD an
    return Response(status_code=200)


@app.post("/login")
def login_submit(request: Request, password: str = Form(...)):
    client_ip = request.client.host if request.client else "unknown"
    if is_login_rate_limited(client_ip):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Zu viele Fehlversuche. Bitte kurz warten und erneut versuchen."},
            status_code=429,
        )
    if not check_password(password):
        record_failed_login(client_ip)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Falsches Passwort"},
            status_code=401,
        )
    reset_login_attempts(client_ip)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
    )
    return response


@app.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/")
def index(request: Request):
    with get_session() as session:
        games = session.exec(select(Game).order_by(Game.position, Game.created_at)).all()
        timer = _timer_snapshot(session)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"games": [g.to_dict() for g in games], "timer": timer},
    )


def _timer_snapshot(session: Session) -> dict:
    timer = session.get(TimerState, 1)
    if timer is None:
        timer = TimerState(id=1)
        session.add(timer)
        session.commit()
        session.refresh(timer)
    now = datetime.now(timezone.utc)
    elapsed = timer.accumulated_seconds
    if timer.running and timer.started_at:
        started_at = timer.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed += (now - started_at).total_seconds()
    return {"running": timer.running, "elapsed_seconds": elapsed, "server_now": now.isoformat()}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if not _is_same_origin(websocket) or not is_valid_session_token(websocket.cookies.get(COOKIE_NAME)):
        await websocket.close(code=4401)
        return

    await manager.connect(websocket)
    await _broadcast_state()
    try:
        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except ValueError:
                logger.warning("Ungültige WebSocket-Nachricht ignoriert")
                continue
            await _handle_action(data)
    finally:
        manager.disconnect(websocket)


def _is_same_origin(websocket: WebSocket) -> bool:
    # Verhindert Cross-Site WebSocket Hijacking: Origin muss zum aufgerufenen Host passen
    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host")
    if not origin or not host:
        return False
    return urlparse(origin).netloc == host


async def _handle_action(data: dict) -> None:
    action = data.get("action")
    try:
        with get_session() as session:
            if action == "add":
                name = (data.get("name") or "").strip()
                target = int(data.get("target") or 0)
                mode = data.get("mode") if data.get("mode") in ("total", "streak") else "total"
                if name and target > 0:
                    existing = session.exec(select(Game)).all()
                    next_position = max((g.position for g in existing), default=-1) + 1
                    session.add(
                        Game(
                            name=name,
                            target_wins=target,
                            current_wins=0,
                            position=next_position,
                            mode=mode,
                        )
                    )
                    session.commit()
            elif action == "increment":
                game = session.get(Game, data.get("id"))
                if game:
                    game.current_wins += 1
                    session.add(game)
                    session.commit()
            elif action == "decrement":
                game = session.get(Game, data.get("id"))
                if game:
                    if game.mode == "streak":
                        game.current_wins = 0  # Niederlage bricht die Serie
                    elif game.current_wins > 0:
                        game.current_wins -= 1
                    session.add(game)
                    session.commit()
            elif action == "update":
                game = session.get(Game, data.get("id"))
                if game:
                    name = (data.get("name") or "").strip()
                    target = data.get("target")
                    if name:
                        game.name = name
                    if target:
                        game.target_wins = max(1, int(target))
                    session.add(game)
                    session.commit()
            elif action == "delete":
                game = session.get(Game, data.get("id"))
                if game:
                    session.delete(game)
                    session.commit()
            elif action == "reorder":
                order = data.get("order") or []
                for index, game_id in enumerate(order):
                    game = session.get(Game, game_id)
                    if game:
                        game.position = index
                        session.add(game)
                session.commit()
            elif action == "timer_toggle":
                timer = session.get(TimerState, 1)
                if timer is None:
                    timer = TimerState(id=1)
                now = datetime.now(timezone.utc)
                if timer.running:
                    started_at = timer.started_at
                    if started_at:
                        if started_at.tzinfo is None:
                            started_at = started_at.replace(tzinfo=timezone.utc)
                        timer.accumulated_seconds += (now - started_at).total_seconds()
                    timer.running = False
                    timer.started_at = None
                else:
                    timer.running = True
                    timer.started_at = now
                session.add(timer)
                session.commit()
            elif action == "timer_reset":
                timer = session.get(TimerState, 1)
                if timer is None:
                    timer = TimerState(id=1)
                timer.running = False
                timer.accumulated_seconds = 0.0
                timer.started_at = None
                session.add(timer)
                session.commit()
    except Exception:
        logger.exception("Fehler beim Verarbeiten der WebSocket-Aktion %r", action)
    await _broadcast_state()


async def _broadcast_state() -> None:
    with get_session() as session:
        games = session.exec(select(Game).order_by(Game.position, Game.created_at)).all()
        timer = _timer_snapshot(session)
    await manager.broadcast({"type": "state", "games": [g.to_dict() for g in games], "timer": timer})

