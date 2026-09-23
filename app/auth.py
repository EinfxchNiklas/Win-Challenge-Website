import os
import secrets
import time
from collections import defaultdict
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
COOKIE_NAME = "session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
USES_DEFAULT_SECRETS = APP_PASSWORD == "changeme" or SECRET_KEY == "dev-secret-change-me"

LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 Minuten

# IP -> Zeitstempel fehlgeschlagener Login-Versuche (nur im Arbeitsspeicher, pro Prozess)
_failed_login_attempts: dict[str, list[float]] = defaultdict(list)

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="win-challenge-auth")


def create_session_token() -> str:
    return _serializer.dumps({"authenticated": True})


def is_valid_session_token(token: Optional[str]) -> bool:
    if not token:
        return False
    try:
        data = _serializer.loads(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return bool(data.get("authenticated"))


def check_password(password: str) -> bool:
    # Zeitkonstanter Vergleich schützt vor Timing-Angriffen auf das Passwort
    return secrets.compare_digest(password, APP_PASSWORD)


def _prune_attempts(ip: str) -> list[float]:
    cutoff = time.monotonic() - LOGIN_WINDOW_SECONDS
    attempts = [t for t in _failed_login_attempts[ip] if t > cutoff]
    _failed_login_attempts[ip] = attempts
    return attempts


def is_login_rate_limited(ip: str) -> bool:
    return len(_prune_attempts(ip)) >= LOGIN_MAX_ATTEMPTS


def record_failed_login(ip: str) -> None:
    _prune_attempts(ip)
    _failed_login_attempts[ip].append(time.monotonic())


def reset_login_attempts(ip: str) -> None:
    _failed_login_attempts.pop(ip, None)
