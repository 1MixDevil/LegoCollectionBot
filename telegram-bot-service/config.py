from dotenv import load_dotenv
import os

load_dotenv()

# === Токен и URL сервисов из .env ===
TOKEN     = os.getenv("TG_TOKEN")
AUTH_IP   = os.getenv("AUTHORIZATION_IP", "localhost")
AUTH_PORT = os.getenv("AUTHORIZATION_PORT", "8000")
COLL_IP   = os.getenv("COLLECTION_IP",    "localhost")
COLL_PORT = os.getenv("COLLECTION_PORT",  "8001")

AUTH_BASE = f"http://{AUTH_IP}:{AUTH_PORT}"
COLL_BASE = f"http://{COLL_IP}:{COLL_PORT}"


RUS_LABELS = {
    "request_price_buy":   "Запрашивать цену покупки",
    "request_price_sale":  "Запрашивать цену продажи",
    "is_seller":           "Продавец",
    "show_description":    "Показывать описание",
    "auto_fill_dates":     "Автозаполнение дат",
}

TOGGLE_FIELDS = list(RUS_LABELS.keys())