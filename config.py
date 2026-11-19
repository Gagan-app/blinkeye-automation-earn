import os
from dotenv import load_dotenv

# Local / Termux testing ke liye .env file (agar maujood ho toh load karega; Railway par env vars seedha milte hain)
load_dotenv()


def _clean_env(value: str | None, default: str = "") -> str:
    if value is None:
        return default
    return value.strip().strip('"').strip("'")


# --- Telegram Bot & Admin ---
BOT_TOKEN: str = _clean_env(os.getenv("BOT_TOKEN"))

# Railway Variables mein ADMIN ya ADMIN_ID dono mein se jo bhi set ho, use safely parse karega
_raw_admin = _clean_env(os.getenv("ADMIN_ID") or os.getenv("ADMIN") or "0")
try:
    ADMIN_ID: int = int(_raw_admin)
except ValueError:
    ADMIN_ID: int = 0

ADMIN: int = ADMIN_ID  # Alias taaki koi bhi naam import ho toh kaam kare

# --- Turso Cloud Database ---
TURSO_URL: str = _clean_env(os.getenv("TURSO_URL"))
TURSO_TOKEN: str = _clean_env(os.getenv("TURSO_TOKEN"))

# --- Webhook & Payment / UPI ---
WEBHOOK_SECRET: str = _clean_env(os.getenv("WEBHOOK_SECRET"))
DEFAULT_UPI_ID: str = _clean_env(os.getenv("DEFAULT_UPI_ID"))

# Optional webhook URL (sender script / external calls ke liye)
WEBHOOK_URL: str = _clean_env(
    os.getenv("WEBHOOK_URL"),
    "https://blinkeye-automation-earn-production.up.railway.app/webhook/payment",
)

# --- Server & Runtime Settings ---
PORT: int = int(_clean_env(os.getenv("PORT"), "8080"))
HOST: str = _clean_env(os.getenv("HOST"), "0.0.0.0")
DEBUG: bool = _clean_env(os.getenv("DEBUG"), "false").lower() in ("1", "true", "yes")
