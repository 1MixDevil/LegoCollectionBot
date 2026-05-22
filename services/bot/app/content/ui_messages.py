"""Тексты для пользователя: только inline-кнопки, без «/add» и т.п."""

# Главное меню
BTN_MAIN_MENU = "команда /menu, «❌ Отмена» или «↩️ В главное меню»"

# Добавление
BTN_ADD = "«➕ Добавить»"
MSG_SESSION_RESET_ADD = (
    f"Сессия прервана. Нажмите {BTN_ADD} в главном меню и выберите режим добавления."
)
MSG_INVALID_PRICE_RESTART = (
    f"Некорректный формат цены. Нажмите {BTN_ADD} и введите данные заново."
)

# Каталог
BTN_UPDATE_CATALOG = "«🔄 Обновить каталог»"
BTN_HELP = "«❓ Помощь»"
BTN_CONTACT_ADMIN = "«✉️ Связаться с администратором»"

MSG_CATALOG_MISSING_PREFIX = (
    f"\n\nСерии может не быть в базе. Админ: {BTN_UPDATE_CATALOG} → префикс "
    "<code>{prefix}</code>. Остальным: {BTN_HELP} → {BTN_CONTACT_ADMIN}."
)

MSG_CATALOG_MISSING_SHORT = (
    f"Сначала загрузите серию ({BTN_UPDATE_CATALOG}) или напишите админу "
    f"({BTN_HELP} → {BTN_CONTACT_ADMIN})."
)

MSG_UPDATE_RETRY = f"Подождите и повторите через {BTN_UPDATE_CATALOG}."
