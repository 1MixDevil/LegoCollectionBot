import re
import os
from io import BytesIO
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
from aiogram.fsm.state import StatesGroup, State
from app.api.collection import get_figure_info
from app.core.config import MAX_SERIALS_PER_REQUEST
from app.keyboards.main import main_kb, nav_kb
from app.services.collage import StarWarsCollageGenerator
from app.states.figures import CreateTierList

router = Router()
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
    text = (
        f"Введите серийные номера фигурок через запятую (,) или точку с запятой (;)."
        f"\nТакже можно ввести __all__ для всех фигурок SW (будут отправлены пачками по {BATCH_SIZE})."
        f"\nМаксимум артикула за раз: {MAX_SERIALS_PER_REQUEST}."
    )
    await message.answer(text, reply_markup=nav_kb())
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
    telegram_id = str(message.from_user.id)

    records = []
    for serial in serials:
        try:
            info = await get_figure_info(telegram_id, serial)
            records.append({"bricklink_id": info["bricklink_id"]})
        except Exception:
            continue

    if not records:
        await message.answer(
            "Не удалось получить информацию ни по одному артикулу.", reply_markup=main_kb
        )
        await state.clear()
        return

    await _generate_and_send_collage(records, telegram_id, title, message)
    await state.clear()


async def _generate_and_send_collage(records, telegram_id, title, message):
    images = await StarWarsCollageGenerator.fetch_and_prepare_images_async(
    records=StarWarsCollageGenerator.filter_by_keyword(
        data=records, name_key='bricklink_id', keyword=''
    ),
    id_key='bricklink_id',
    prefix_url='https://img.bricklink.com/ItemImage/MN/0',
    min_height=1050,
    font_path='arial.ttf',
    font_size=90,
    max_connections=10,  # подстройте при необходимости
)

    if not images:
        await message.answer(
            f"Не удалось загрузить изображения для тир-листа{f' {title}' if title else ''}.", reply_markup=main_kb
        )
        return
    MAX_FILENAME_LEN = 255   
    base_name = f"tierlist_{telegram_id}{f'_{title}' if title else ''}.png"

    if len(base_name) > MAX_FILENAME_LEN:
        max_title_len = MAX_FILENAME_LEN - len(f"tierlist_{telegram_id}_.png")
        title = title[:max_title_len]
        base_name = f"tierlist_{telegram_id}_{title}.png"

    output_path = os.path.join(TMP_DIR, base_name)

    await StarWarsCollageGenerator.create_collage_async(
    images=images,
    output_path=output_path,
    columns=5,
    title=title
)


    try:
        with open(output_path, 'rb') as f:
            doc = BufferedInputFile(f.read(), filename=base_name)
        await message.answer_document(doc, caption=f"Ваш тир-лист {title or ''} готов!", reply_markup=main_kb)
    except Exception as e:
        await message.answer(
            f"Ошибка отправки файла тир-листа{f' {title}' if title else ''}. {e}", reply_markup=main_kb
        )
    finally:
        try:
            os.remove(output_path)
        except:
            pass
