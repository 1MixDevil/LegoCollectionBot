# import os
# import asyncio
# import logging

# from aiogram import Bot, Dispatcher, types
# from aiogram.filters.command import Command
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import StatesGroup, State
# from aiogram.types import InputFile
# import tempfile

# from PIL import Image
# from io import BytesIO
# from aiogram.types import BufferedInputFile
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from typing import Optional

# import httpx

# from businessLogic.collage import StarWarsCollageGenerator
# from inlineKeyBoards import main_kb, confirm_kb, make_info_kb, nav_kb
# from config import TOKEN, AUTH_BASE, AUTH_IP, AUTH_PORT, COLL_BASE, COLL_IP, COLL_PORT, RUS_LABELS, TOGGLE_FIELDS
# from FMSState import AddFigureState, UpdateFigures, DeleteFigures, InfoFigures
# from HttpRequests import (get_user_settings, create_user, add_figure_to_user, delete_figure_to_user,
#                           create_user, add_figure_to_user, delete_figure_to_user, list_user_figures, update_figures_list)

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# bot = Bot(token=TOKEN)
# dp = Dispatcher()


# # === Handlers ===

# @dp.message(Command("start"))
# async def cmd_start(message: types.Message, state: FSMContext):
#     tg_id = str(message.from_user.id)
#     name  = message.from_user.first_name or "пользователь"
#     try:
#         created = await create_user(tg_id, name)
#     except Exception:
#         await message.answer("Ошибка при связывании с сервисом авторизации.")
#         return

#     if created:
#         await message.answer(f"Привет, {name}! Ваш аккаунт создан.", reply_markup=main_kb)
#     else:
#         await message.answer(f"С возвращением, {name}!", reply_markup=main_kb)

# @dp.callback_query(lambda cb: cb.data == "add")
# async def cb_add(call: types.CallbackQuery, state: FSMContext):
#     await call.message.answer("Введите артикул (bricklink_id) фигурки:")
#     await call.message.delete_reply_markup()
#     await state.set_state(AddFigureState.waiting_serial)

# @dp.message(AddFigureState.waiting_serial)
# async def add_serial(message: types.Message, state: FSMContext):
#     serial = message.text.strip()
#     tg_id = str(message.from_user.id)

#     # Получаем настройки пользователя
#     try:
#         settings = await get_user_settings(tg_id)
#     except Exception:
#         await message.answer("Ошибка получения настроек пользователя.", reply_markup=main_kb)
#         await state.clear()
#         return

#     # Сохраняем serial и user_id в FSM-состоянии
#     await state.update_data(serial=serial, user_id=tg_id, settings=settings)

#     # Дальше — проверяем настройки и запрашиваем данные по порядку
#     if settings.get("request_price_buy"):
#         await message.answer("Введите цену покупки:")
#         await state.set_state(AddFigureState.request_price_buy)
#     elif settings.get("request_price_sale"):
#         await message.answer("Введите цену продажи:")
#         await state.set_state(AddFigureState.request_price_sale)
#     elif settings.get("show_description"):
#         await message.answer("Введите описание фигурки:")
#         await state.set_state(AddFigureState.show_description)
#     elif settings.get("auto_fill_dates"):
#         await finish_add_figure(message, state)
#     else:
#         await finish_add_figure(message, state)

# @dp.message(AddFigureState.request_price_buy)
# async def handle_price_buy(message: types.Message, state: FSMContext):
#     await state.update_data(price_buy=message.text.strip())
#     data = await state.get_data()
#     if data["settings"].get("request_price_sale"):
#         await message.answer("Введите цену продажи:")
#         await state.set_state(AddFigureState.request_price_sale)
#     elif data["settings"].get("show_description"):
#         await message.answer("Введите описание фигурки:")
#         await state.set_state(AddFigureState.show_description)
#     else:
#         await finish_add_figure(message, state)


# @dp.message(AddFigureState.request_price_sale)
# async def handle_price_sale(message: types.Message, state: FSMContext):
#     await state.update_data(price_sale=message.text.strip())
#     data = await state.get_data()
#     if data["settings"].get("show_description"):
#         await message.answer("Введите описание фигурки:")
#         await state.set_state(AddFigureState.show_description)
#     else:
#         await finish_add_figure(message, state)


# @dp.message(AddFigureState.show_description)
# async def handle_description(message: types.Message, state: FSMContext):
#     await state.update_data(description=message.text.strip())
#     await finish_add_figure(message, state)

# async def finish_add_figure(message: types.Message, state: FSMContext):
#     data = await state.get_data()
#     settings = data["settings"]
#     payload = {
#         "user_id": data["user_id"],
#         "bricklink_id": data["serial"],
#         "price_buy": data.get("price_buy"),
#         "price_sale": data.get("price_sale"),
#         "description": data.get("description"),
#         "buy_date": None,
#         "sale_date": None
#     }

#     if settings.get("auto_fill_dates"):
#         from datetime import date
#         if payload["price_buy"] is not None:
#             payload["buy_date"] = date.today().isoformat()
#         if payload["price_sale"] is not None:
#             payload["sale_date"] = date.today().isoformat()

#     try:
#         await add_figure_to_user(**payload)
#         await message.answer("Фигурка успешно добавлена в вашу коллекцию.", reply_markup=main_kb)
#     except Exception as e:
#         await message.answer(f"Ошибка при добавлении фигурки: {e}", reply_markup=main_kb)
#     finally:
#         await state.clear()


# @dp.callback_query(lambda cb: cb.data == "my_collection")
# async def cb_my_collection(call: types.CallbackQuery):
#     await call.answer()
#     user_id = str(call.from_user.id)

#     # 1) Получаем записи
#     records = await list_user_figures(user_id)
#     if not records:
#         return await call.message.answer("Ваша коллекция пуста.", reply_markup=main_kb)

#     # 2) Фильтрация и скачивание + подготовка изображений
#     #    (можно передавать пустой keyword, тогда вернётся весь список)
#     filtered = records  # или применить фильтр по ключевому слову

#     # 3) Генерация коллажа в память
#     images = StarWarsCollageGenerator.fetch_and_prepare_images(
#         records=StarWarsCollageGenerator.filter_by_keyword(filtered, name_key='name', keyword=''),
#         id_key='bricklink_id',
#         prefix_url='https://img.bricklink.com/ItemImage/MN/0/',
#         min_height=1050,
#         font_path='arial.ttf',
#         font_size=90,
#     )

#     if not images:
#         return await call.message.answer("Не удалось подготовить изображения.", reply_markup=main_kb)

#     # собираем коллаж в объект PIL.Image
#     # (внутри – как в create_collage, но возвращаем объект вместо сохранения)
#     def build_collage_image(img_list, columns=5, max_images=None):
#         imgs = img_list[:max_images] if max_images else img_list
#         count = len(imgs)
#         rows = (count + columns - 1) // columns
#         w = max(im.width for im in imgs)
#         h = max(im.height for im in imgs)
#         collage = Image.new('RGB', (w * columns, h * rows), (255, 255, 255))
#         for idx, im in enumerate(imgs):
#             x = (idx % columns) * w
#             y = (idx // columns) * h
#             collage.paste(im, (x, y))
#         return collage

#     collage_img = build_collage_image(images, columns=5, max_images=None)

#     # сохраняем в BytesIO
#     buf = BytesIO()
#     collage_img.save(buf, format='PNG')
#     buf.seek(0)

#     # 4) Отправляем коллаж как документ (без сжатия)
#     document = BufferedInputFile(buf.read(), filename="my_collection.png")

#     await bot.send_document(
#         chat_id=call.from_user.id,
#         document=document,
#         caption="Вот ваша коллекция!",
#         reply_markup=main_kb
#     )



# @dp.callback_query(lambda cb: cb.data == "update")
# async def cb_update(call: types.CallbackQuery, state: FSMContext):
#     try:
#         await call.message.answer("Введите артикул типа фигурки (sw, lor):")
#         await call.message.delete_reply_markup()
#         await state.set_state(UpdateFigures.waiting_article)
#     except Exception:
#         await call.message.answer("Произошла ошибка", reply_markup=main_kb)

# @dp.message(UpdateFigures.waiting_article)
# async def get_article(message: types.Message, state: FSMContext):
#     article = message.text.strip()
#     try:
#         rec = await update_figures_list(article=article)
#     except httpx.HTTPStatusError as e:
#         await message.answer(f"Ошибка сервиса коллекции: {e.response.status_code}", reply_markup=main_kb)
#     except Exception as e:
#         await message.answer(f"Не удалось обновить фигуры: {e}", reply_markup=main_kb)
#     else:
#         await message.answer(f"Обновление по «{article}» запущено.", reply_markup=main_kb)
#     finally:
#         # Очищаем состояние
#         await state.clear()



# @dp.callback_query(lambda cb: cb.data == "delete")
# async def cb_update(call: types.CallbackQuery, state: FSMContext):
#     try:
#         await call.message.answer("Введите артикул типа фигурки (sw, lor):")
#         await call.message.delete_reply_markup()
#         await state.set_state(DeleteFigures.waiting_serial)
#     except Exception:
#         await call.message.answer("Произошла ошибка", reply_markup=main_kb)

# @dp.message(DeleteFigures.waiting_serial)
# async def get_delete_figure(message: types.Message, state: FSMContext):
#     serial = message.text.strip()
#     user_id = str(message.from_user.id)
#     try:
#         rec = await delete_figure_to_user(serial, user_id)
#     except httpx.HTTPStatusError as e:
#         await message.answer(f"Ошибка сервиса коллекции: {e.response.status_code}", reply_markup=main_kb)
#     except Exception:
#         await message.answer("Не удалось удалить фигурку.", reply_markup=main_kb)
#     else:
#         await message.answer(f"Фигурка {serial} удалена из вашей коллекции.", reply_markup=main_kb)
#     finally:
#         await state.clear()


# @dp.callback_query(lambda cb: cb.data == "settings")
# async def cb_settings(call: types.CallbackQuery):
#     tg_id = call.from_user.id

#     # 1) GET всех настроек
#     async with httpx.AsyncClient() as client:
#         r = await client.get(f"{AUTH_BASE}/users/get_user_settings/{tg_id}")
#         r.raise_for_status()
#         settings = r.json()

#     db_user_id = settings["user_id"]

#     # 2) Собираем inline_keyboard вручную: одна кнопка = один список = одна строка
#     inline_keyboard = []
#     for field in TOGGLE_FIELDS:
#         curr = settings.get(field, False)
#         label = RUS_LABELS[field]
#         text = ("✅ " if curr else "❌ ") + label
#         cb_data = f"settings:{db_user_id}:{field}:{int(not curr)}"
#         btn = types.InlineKeyboardButton(text=text, callback_data=cb_data)
#         inline_keyboard.append([btn])  # каждый btn — в своей строке

#     # добавляем кнопку «Закрыть» в отдельную строку
#     close_btn = types.InlineKeyboardButton(text="Закрыть", callback_data="settings:close")
#     inline_keyboard.append([close_btn])

#     kb = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

#     # отправляем одно сообщение с клавиатурой
#     await call.message.answer("Настройки пользователя:", reply_markup=kb)
#     await call.answer()


# @dp.callback_query(lambda cb: cb.data and cb.data.startswith("settings:"))
# async def cb_settings_toggle(call: types.CallbackQuery):
#     parts = call.data.split(":")
#     # settings:close
#     if parts[1] == "close":
#         await call.message.edit_text(
#             "Вы вернулись в главное меню. Выберите действие:",
#             reply_markup=main_kb
#         )
#         return await call.answer()
#     # settings:<db_user_id>:<field>:<new_val>
#     _, db_user_id, field, new_val = parts
#     db_user_id = int(db_user_id)
#     new_value = bool(int(new_val))

#     # 1) PUT обновлённых настроек
#     payload = {"user_id": db_user_id, field: new_value}
#     async with httpx.AsyncClient() as client:
#         await client.put(f"{AUTH_BASE}/users/update_user_settings/", json=payload)

#     # 2) GET заново для актуализации
#     async with httpx.AsyncClient() as client:
#         r = await client.get(f"{AUTH_BASE}/users/get_user_settings/{call.from_user.id}")
#         r.raise_for_status()
#         settings = r.json()

#     # 3) Собираем клавиатуру заново (по одной кнопке в строке)
#     inline_keyboard = []
#     for fld in TOGGLE_FIELDS:
#         curr = settings.get(fld, False)
#         label = RUS_LABELS[fld]
#         text = ("✅ " if curr else "❌ ") + label
#         cb_data = f"settings:{db_user_id}:{fld}:{int(not curr)}"
#         inline_keyboard.append([ types.InlineKeyboardButton(text=text, callback_data=cb_data) ])

#     inline_keyboard.append([ types.InlineKeyboardButton(text="Закрыть", callback_data="settings:close") ])

#     kb = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

#     # обновляем только клавиатуру (текст остаётся "Настройки пользователя:")
#     await call.message.edit_reply_markup(reply_markup=kb)

#     # 4) короткий отзыв на русском
#     action = "включено" if new_value else "выключено"
#     await call.answer(f"{RUS_LABELS[field]} {action}")


# @dp.callback_query(lambda cb: cb.data == "info")
# async def cb_info(call: types.CallbackQuery, state: FSMContext):
#     await call.message.answer(
#         "Введите серийный номер фигурки, о которой хотите получить информацию:"
#     )
#     await call.message.delete_reply_markup()
#     await state.set_state(InfoFigures.waiting_serial)


# @dp.message(InfoFigures.waiting_serial)
# async def get_info_figure(message: types.Message, state: FSMContext):
#     serial = message.text.strip()
#     user_id = str(message.from_user.id)

#     # 1) GET /figure/info/
#     try:
#         async with httpx.AsyncClient() as client:
#             r = await client.get(
#                 f"{COLL_BASE}/figure/info/",
#                 params={"user_id": int(user_id), "bricklink_id": serial}
#             )
#             r.raise_for_status()
#             info = r.json()
#     except httpx.HTTPStatusError as e:
#         # если нет такой фигурки
#         if e.response.status_code == 404:
#             await message.answer("Фигурка не найдена.", reply_markup=main_kb)
#         else:
#             await message.answer(f"Ошибка сервиса: {e.response.status_code}", reply_markup=main_kb)
#         await state.clear()
#         return
#     except Exception as e:
#         await message.answer(f"Не удалось получить информацию: {e}", reply_markup=main_kb)
#         await state.clear()
#         return

#     # 2) Формируем текст
#     user_rec = info.get("user_record")
#     user_rec = {} if user_rec is None else user_rec
#     text = (
#         f"🔍 <b>{info['name']}</b>\n"
#         f"• Артикул: <code>{info['bricklink_id']}</code>\n"
#         f"• Цена покупки: {user_rec.get('price_buy') or '–'}\n"
#         f"• Цена продажи: {user_rec.get('price_sale') or '–'}\n"
#         f"• Описание: {user_rec.get('description') or '–'}\n"
#         f"• Дата покупки: {user_rec.get('buy_date') or '–'}\n"
#         f"• Дата продажи: {user_rec.get('sale_date') or '–'}"
#     )

#     # 3) Кнопки действий
#     kb = make_info_kb(serial)

#     # Отправляем картинку + подпись
#     photo_url = f"https://img.bricklink.com/ItemImage/MN/0/{serial}.png"
#     await send_figure_image(
#         chat_id=message.chat.id,
#         url=photo_url,
#         caption=text,
#         reply_markup=kb
#     )

#     await state.clear()


# async def send_figure_image(chat_id: int, url: str, caption: str, reply_markup):
#     # 1) Скачиваем картинку с нужными заголовками
#     headers = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
#     }
#     async with httpx.AsyncClient(headers=headers) as client:
#         r = await client.get(url)
#         r.raise_for_status()
#         data = r.content

#     # 2) Упаковываем в BufferedInputFile
#     bio = BytesIO(data)
#     bio.name = url.split("/")[-1]  # например "sw0123.png"
#     bio.seek(0)
#     file = BufferedInputFile(bio.read(), filename=bio.name)

#     # 3) Отправляем фото
#     await bot.send_photo(
#         chat_id=chat_id,
#         photo=file,
#         caption=caption,
#         parse_mode="HTML",
#         reply_markup=reply_markup
#     )


# # === Обработка кнопок info_action ===
# @dp.callback_query(lambda cb: cb.data and cb.data.startswith("info_action:"))
# async def cb_info_actions(call: types.CallbackQuery):
#     _, action, serial = call.data.split(":")
#     user_id = str(call.from_user.id)

#     if action == "wishlist":
#         # TODO: ваш код добавления в список желаемого
#         await call.answer("Добавлено в список желаемого!", show_alert=True)

#     elif action == "buy":
#         # TODO: ваш код покупки (или перевод в режим FSM для ввода цены)
#         await call.answer("Режим покупки не реализован.", show_alert=True)

#     elif action == "sell":
#         # TODO: ваш код продажи
#         await call.answer("Режим продажи не реализован.", show_alert=True)

#     elif action == "add":
#         # повторно добавить в коллекцию
#         try:
#             await add_figure_to_user(bricklink_id=serial, user_id=user_id)
#             await call.answer("Фигурка добавлена в коллекцию!", show_alert=True)
#         except Exception:
#             await call.answer("Ошибка при добавлении.", show_alert=True)

#     elif action == "delete":
#         try:
#             await delete_figure_to_user(serial, user_id)
#             await call.answer("Фигурка удалена из коллекции!", show_alert=True)
#         except Exception:
#             await call.answer("Ошибка при удалении.", show_alert=True)

#     # не меняем текст, просто закрываем тултип
#     await call.answer()


# @dp.callback_query(lambda cb: cb.data == "cancel")
# async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
#     await state.clear()  # сброс всех состояний
#     await call.message.edit_text("❌ Действие отменено.", reply_markup=main_kb)
#     await call.answer()

# @dp.callback_query(lambda cb: cb.data == "back_to_serial")
# async def cb_back_to_serial(call: types.CallbackQuery, state: FSMContext):
#     # Возвращаемся на этап ввода артикула
#     await state.set_state(AddFigureState.waiting_serial)
#     await call.message.edit_text("Введите артикул (bricklink_id) фигурки:", reply_markup=nav_kb())
#     await call.answer()

# # === Запуск ===
# async def main():
#     await dp.start_polling(bot)

# if __name__ == "__main__":
#     asyncio.run(main())


import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters.command import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import TOKEN
from HttpRequests import create_user
from inlineKeyBoards import main_kb

# импортируем роутеры из handlers/
from handlers.add_figure import router as add_figure_router
from handlers.my_collection import router as my_collection_router
from handlers.update_figures import router as update_figures_router
from handlers.delete_figure import router as delete_figure_router
from handlers.settings import router as settings_router
from handlers.info_figure import router as info_figure_router

# === Стартовый хэндлер пока оставляем в main.py ===
async def cmd_start(message: Message, state: FSMContext):
    tg_id = str(message.from_user.id)
    name  = message.from_user.first_name or "пользователь"
    try:
        created = await create_user(tg_id, name)
    except Exception:
        await message.answer("Ошибка при связывании с сервисом авторизации.")
        return

    if created:
        await message.answer(f"Привет, {name}! Ваш аккаунт создан.", reply_markup=main_kb)
    else:
        await message.answer(f"С возвращением, {name}!", reply_markup=main_kb)

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # регистрируем стартовый хэндлер
    dp.message.register(cmd_start, Command("start"))

    # регистрируем все роутеры‑модули
    dp.include_router(add_figure_router)
    dp.include_router(my_collection_router)
    dp.include_router(update_figures_router)
    dp.include_router(delete_figure_router)
    dp.include_router(settings_router)
    dp.include_router(info_figure_router)

    # запускаем поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
