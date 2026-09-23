import os
import secrets
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
COOKIE_NAME = "session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
USES_DEFAULT_SECRETS = APP_PASSWORD == "changeme" or SECRET_KEY == "dev-secret-change-me"

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
