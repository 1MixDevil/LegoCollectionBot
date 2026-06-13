import os

from dotenv import load_dotenv

load_dotenv()

TG_TOKEN = os.getenv("TG_TOKEN", "")

AUTH_HOST = os.getenv("AUTHORIZATION_IP", "auth-service")
AUTH_PORT = os.getenv("AUTHORIZATION_PORT", "8000")
COLLECTION_HOST = os.getenv("COLLECTION_IP", "collection-service")
COLLECTION_PORT = os.getenv("COLLECTION_PORT", "8001")

AUTH_BASE_URL = f"http://{AUTH_HOST}:{AUTH_PORT}"
COLLECTION_BASE_URL = f"http://{COLLECTION_HOST}:{COLLECTION_PORT}"

RUS_LABELS = {
    "request_price_buy": "Запрашивать цену покупки",
    "request_price_sale": "Запрашивать цену продажи",
    "show_description": "Показывать описание",
    "auto_fill_dates": "Автозаполнение дат",
}

SETTING_HINTS = {
    "request_price_buy": "При добавлении одной фигурки спрашивать цену покупки.",
    "request_price_sale": "При добавлении одной фигурки спрашивать цену продажи.",
    "show_description": "При добавлении одной фигурки спрашивать описание.",
    "auto_fill_dates": "Подставлять сегодняшнюю дату, если указана цена.",
}

TOGGLE_FIELDS = list(RUS_LABELS.keys())

MAX_SERIALS_PER_REQUEST = int(os.getenv("MAX_SERIALS_PER_REQUEST", "50"))
