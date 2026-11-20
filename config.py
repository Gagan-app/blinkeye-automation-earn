Import os
from dotenv import load_dotenv

load_dotenv()


def _clean_env(value: str | None, default: str = "") -> str:
    if value is None:
        return default
    return value.strip().strip('"').strip("'")


# --- Telegram Bot & Admin ---
BOT_TOKEN: str = _clean_env(
    os.getenv("BOT_TOKEN"),
    "9025362287:AAFFVv7r4xNNDlRILofEKekZz8rvXtxMAJM",
)

_raw_admin = _clean_env(
    os.getenv("ADMIN_ID") or os.getenv("ADMIN") or "8122669942"
)
try:
    ADMIN_ID: int = int(_raw_admin)
except ValueError:
    ADMIN_ID: int = 8122669942

ADMIN: int = ADMIN_ID

# --- Turso Cloud Database ---
TURSO_URL: str = _clean_env(
    os.getenv("TURSO_URL"),
    "libsql://blinkeye-automation-earn-gaganllc.aws-ap-south-1.turso.io",
)
TURSO_TOKEN: str = _clean_env(
    os.getenv("TURSO_TOKEN"),
    "jEtMDgwMS03YTBiLTg0NzItYTM5ZWM0MDIzOGNiIiwia2lkIjoiNTRfWjhvUlpPbUFmTEZuSzRRS1I2dlhMcE5IbzRXQVRDRFFMSW55QkpQUSIsInJpZCI6IjUxMDljNDMzLTMxYjItNGJhZC1hYWMxLTE4NjY0MWNiYjg2NCJ9.SFXXwYsniImEw-296IMmCMSJaI2E3ZxLTzDgr4PWhvkRCdPPSGWtxJRQNMWciRdHlDGY14_BK2fJ4WvJxcGfAQ",
)

# --- Webhook & Payment / UPI ---
WEBHOOK_SECRET: str = _clean_env(
    os.getenv("WEBHOOK_SECRET"),
    "blinkeyes_pay_98f7a2g99",
)
DEFAULT_UPI_ID: str = _clean_env(
    os.getenv("Q031118787@ybl"),
    "",
)

_raw_webhook_url = _clean_env(
    os.getenv("WEBHOOK_URL"),
    "https://blinkeye-automation-earn-production.up.railway.app/webhook/payment",
)
if _raw_webhook_url and not _raw_webhook_url.startswith(("http://", "https://")):
    _raw_webhook_url = f"https://{_raw_webhook_url}"
if _raw_webhook_url and not _raw_webhook_url.endswith("/webhook/payment"):
    _raw_webhook_url = f"{_raw_webhook_url.rstrip('/')}/webhook/payment"

WEBHOOK_URL: str = _raw_webhook_url

# --- Google / YouTube OAuth Settings ---
CLIENT_SECRETS_FILE: str = _clean_env(
    os.getenv("CLIENT_SECRETS_FILE"),
    "client_secrets.json",
)
TOKEN_FILE: str = _clean_env(
    os.getenv("client_secret":"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","redirect_uris":["https://localhost"]}}"),
    "token.json",
)

# --- Server & Runtime Settings ---
PORT: int = int(_clean_env(os.getenv("PORT"), "8080"))
HOST: str = _clean_env(os.getenv("HOST"), "0.0.0.0")
DEBUG: bool = _clean_env(os.getenv("DEBUG"), "false").lower() in ("1", "true", "yes")
