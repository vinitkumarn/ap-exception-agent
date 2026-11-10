"""Settings read from environment variables (.env in development).

Read fresh on every call so tests can change env vars safely.
"""
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional
    pass

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    backend: str
    db_path: str
    model: str
    max_steps: int
    price_in: float
    price_out: float


def get_settings() -> Settings:
    db_path = os.getenv("APAGENT_DB_PATH", "data/ap.db")
    if not Path(db_path).is_absolute():
        db_path = str(ROOT / db_path)
    return Settings(
        backend=os.getenv("APAGENT_BACKEND", "sqlite").lower(),
        db_path=db_path,
        model=os.getenv("APAGENT_MODEL", "claude-sonnet-5-5"),
        max_steps=int(os.getenv("APAGENT_MAX_STEPS", "8")),
        price_in=float(os.getenv("APAGENT_PRICE_IN_PER_MTOK", "0") or 0),
        price_out=float(os.getenv("APAGENT_PRICE_OUT_PER_MTOK", "0") or 0),
    )
