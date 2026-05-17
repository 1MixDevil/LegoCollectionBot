from aiogram.fsm.state import State, StatesGroup


class AddFigureState(StatesGroup):
    waiting_serial = State()
    request_price_buy = State()
    request_price_sale = State()
    show_description = State()


class BulkAddState(StatesGroup):
    waiting_serials = State()


class UpdateFigures(StatesGroup):
    waiting_article = State()


class DeleteFigures(StatesGroup):
    waiting_serial = State()


class InfoFigures(StatesGroup):
    waiting_serial = State()


class PhotoSearchState(StatesGroup):
    waiting_photo = State()


class CreateTierList(StatesGroup):
    waiting_name_list = State()
    waiting_serials = State()
