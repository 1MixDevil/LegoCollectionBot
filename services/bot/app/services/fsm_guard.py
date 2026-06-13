"""Проверки FSM: когда не перехватывать глобальные обработчики."""

from aiogram.fsm.context import FSMContext

from app.states.figures import (
    AddFigureState,
    AdminPanelState,
    BulkAddState,
    CreateTierList,
    DeleteFigures,
    HelpState,
    InfoFigures,
    PhotoSearchState,
    UpdateFigures,
)

# Состояния, в которых фото не должно запускать auto-поиск
_BLOCKING_PHOTO_STATES = frozenset(
    {
        AddFigureState.waiting_serial.state,
        AddFigureState.request_price_buy.state,
        AddFigureState.request_price_sale.state,
        AddFigureState.show_description.state,
        BulkAddState.waiting_serials.state,
        InfoFigures.waiting_serial.state,
        InfoFigures.waiting_edit_pick.state,
        InfoFigures.waiting_edit_value.state,
        CreateTierList.waiting_name_list.state,
        CreateTierList.waiting_mode.state,
        CreateTierList.waiting_serials.state,
        CreateTierList.waiting_mark_owned.state,
        HelpState.waiting_admin_message.state,
        AdminPanelState.waiting_telegram_id.state,
        UpdateFigures.waiting_article.state,
        DeleteFigures.waiting_serial.state,
        PhotoSearchState.waiting_photo.state,
    }
)


async def allows_global_photo_search(state: FSMContext) -> bool:
    current = await state.get_state()
    if current is None:
        return True
    return current not in _BLOCKING_PHOTO_STATES
