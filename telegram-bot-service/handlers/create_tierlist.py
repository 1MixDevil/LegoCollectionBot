import re
import os
from io import BytesIO
import httpx
import asyncio
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from aiogram.fsm.state import StatesGroup, State
from businessLogic.collage import StarWarsCollageGenerator
from inlineKeyBoards import nav_kb, main_kb
from FMSState import CreateTierList
from config import COLL_BASE

router = Router()
MAX_SERIALS_PER_REQUEST = int(os.getenv("MAX_SERIALS_PER_REQUEST", 50))
TMP_DIR = os.getenv("TMP_DIR", "/tmp")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))
CONCURRENT_BATCHES = int(os.getenv("CONCURRENT_BATCHES", 5))


@router.callback_query(lambda cb: cb.data == "create_tierlist")
async def cb_start_tierlist(call: types.CallbackQuery, state: FSMContext):
    """Запрашиваем у пользователя название тир-листа"""
    await call.answer()
    await call.message.answer(
        "Введите название вашего Tier List.\n"
        "Если не нужно — отправьте `null`."
    )
    await state.set_state(CreateTierList.waiting_name_list)


@router.message(CreateTierList.waiting_name_list)
async def on_name_entered(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if name.lower() == 'null':
        name = None
    await state.update_data(title=name)

    # Переходим к запросу серийников
    from inlineKeyBoards import tierlist_kb
    text = (
        f"Введите серийные номера фигурок через запятую (,) или точку с запятой (;)."
        f"\nТакже можно ввести __all__ для всех фигурок SW (будут отправлены пачками по {BATCH_SIZE})."
        f"\nМаксимум артикула за раз: {MAX_SERIALS_PER_REQUEST}."
    )
    await message.answer(text, reply_markup=tierlist_kb())
    await state.set_state(CreateTierList.waiting_serials)


@router.message(CreateTierList.waiting_serials)
async def on_serials_entered(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data.get('title') or ''

    text = message.text.strip()
    serials = [s.strip() for s in re.split(r"[,;\s]+", text) if s.strip()]
    if not serials:
        await message.answer("Не введён ни один артикул.", reply_markup=nav_kb())
        await state.clear()
        return

    if len(serials) > MAX_SERIALS_PER_REQUEST:
        await message.answer(
            f"❗️ Максимум {MAX_SERIALS_PER_REQUEST} артикула за раз.", reply_markup=nav_kb()
        )
        await state.set_state(CreateTierList.waiting_serials)
        return

    await message.answer("Генерируем ваш тир-лист, подождите...", reply_markup=main_kb)
    user_id = str(message.from_user.id)

    records = []
    async with httpx.AsyncClient() as client:
        for serial in serials:
            try:
                r = await client.get(
                    f"{COLL_BASE}/figure/info/",
                    params={"user_id": user_id, "bricklink_id": serial}
                )
                if r.status_code != 200:
                    continue
                info = r.json()
                records.append({"bricklink_id": info['bricklink_id']})
            except:
                continue

    if not records:
        await message.answer(
            "Не удалось получить информацию ни по одному артикулу.", reply_markup=main_kb
        )
        await state.clear()
        return

    await _generate_and_send_collage(records, user_id, title, message)
    await state.clear()


async def _generate_and_send_collage(records, user_id, title, message):
    loop = asyncio.get_running_loop()
    images = await loop.run_in_executor(
        None,
        lambda: StarWarsCollageGenerator.fetch_and_prepare_images(
            records=StarWarsCollageGenerator.filter_by_keyword(
                data=records, name_key='bricklink_id', keyword=''
            ),
            id_key='bricklink_id', prefix_url='https://img.bricklink.com/ItemImage/MN/0',
            min_height=1050, font_path='arial.ttf', font_size=90
        )
    )
    if not images:
        await message.answer(
            f"Не удалось загрузить изображения для тир-листа{f' {title}' if title else ''}.", reply_markup=main_kb
        )
        return

    output_name = f"tierlist_{user_id}{f'_{title}' if title else ''}.png"
    output_path = os.path.join(TMP_DIR, output_name)
    await loop.run_in_executor(
        None,
        lambda: StarWarsCollageGenerator.create_collage(
            images=images,
            output_path=output_path,
            columns=5,
            title=title
        )
    )

    try:
        with open(output_path, 'rb') as f:
            doc = BufferedInputFile(f.read(), filename=output_name)
        await message.answer_document(doc, caption=f"Ваш тир-лист {title or ''} готов!", reply_markup=main_kb)
    except:
        await message.answer(
            f"Ошибка отправки файла тир-листа{f' {title}' if title else ''}.", reply_markup=main_kb
        )
    finally:
        try:
            os.remove(output_path)
        except:
            pass
