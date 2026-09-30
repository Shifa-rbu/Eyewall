import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        gemini_api_key: str | None = None
        gee_service_account: str | None = None
        eyewall_db: Path = ROOT / ".runtime" / "eyewall.sqlite3"
        model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    settings = Settings()
    DB_PATH = settings.eyewall_db
    GEMINI_API_KEY = settings.gemini_api_key
    GEE_SERVICE_ACCOUNT = settings.gee_service_account
except ImportError:
    # Keeps the static/keyless mode importable before optional setup deps land.
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))
    DB_PATH = Path(os.environ.get("EYEWALL_DB", ROOT / ".runtime" / "eyewall.sqlite3"))
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEE_SERVICE_ACCOUNT = os.environ.get("GEE_SERVICE_ACCOUNT")
