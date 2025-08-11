from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import Message, CallbackQuery

class FallbackMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        handled = False

        async def mark_handled(*args, **kwargs):
            nonlocal handled
            handled = True
            return await handler(*args, **kwargs)

        result = await mark_handled(event, data)

        # Если это сообщение и оно никем не обработано
        if not handled:
            if isinstance(event, Message):
                await event.answer("Функционал пока в разработке...")
            elif isinstance(event, CallbackQuery):
                await event.answer("Функционал пока в разработке...", show_alert=True)

        return result
