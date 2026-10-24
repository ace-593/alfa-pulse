from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Actor:
    id: str
    session_id: str
    admin: bool = False


@dataclass
class User:
    id: str
    email: str
    display_name: str
    password_hash: str
    admin: bool = False


@dataclass
class Session:
    id: str
    user_id: str
    expires_at: datetime
    revoked: bool = False


def now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None = None) -> str:
    return (value or now()).isoformat().replace("+00:00", "Z")
