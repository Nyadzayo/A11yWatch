from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from a11ywatch.core.config import settings

# bcrypt only considers the first 72 bytes of a password.
_MAX_BCRYPT_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:_MAX_BCRYPT_BYTES],
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_ttl_minutes)
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None
