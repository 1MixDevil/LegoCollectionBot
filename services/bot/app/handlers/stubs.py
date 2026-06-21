"""Заглушки для кнопок, которые ещё не реализованы."""

from aiogram import F, Router, types

from app.core.access import ensure_access

router = Router()

STUB_MESSAGE = "Функционал пока не реализован."

# Точные callback_data из главного меню и подменю
STUB_CALLBACKS = frozenset({
    "marketplace",
    "my_listings",
    "browse_listings",
    "premium",
    "bind_bricklink",
    "toggle_notifications",
    "list_tierlists",
})

STUB_FEATURES = {
    "marketplace": "marketplace",
    "my_listings": "marketplace",
    "browse_listings": "marketplace",
}


@router.callback_query(F.data.in_(STUB_CALLBACKS))
async def cb_not_implemented_exact(call: types.CallbackQuery) -> None:
    feature = STUB_FEATURES.get(call.data)
    if feature and not await ensure_access(call, feature):
        return
    await call.answer(STUB_MESSAGE, show_alert=True)


def _tierlist_stub(data: str) -> bool:
    return bool(
        data
        and (
            data.startswith("add_to_tierlist:")
            or data.startswith("remove_from_tierlist:")
            or data.startswith("export_tierlist_excel:")
            or data.startswith("rename_tierlist:")
            or data.startswith("show_collage:")
        )
    )


@router.callback_query(lambda cb: _tierlist_stub(cb.data))
async def cb_not_implemented_tierlist(call: types.CallbackQuery) -> None:
    await call.answer(STUB_MESSAGE, show_alert=True)
