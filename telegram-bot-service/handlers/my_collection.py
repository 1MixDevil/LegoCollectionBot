# handlers_collection.py
import os
import tempfile
import logging
from io import BytesIO

from aiogram import Router, types
from aiogram.types import BufferedInputFile

import pandas as pd
from PIL import Image

from HttpRequests import list_user_figures, clear_user_collection
from businessLogic.collage import StarWarsCollageGenerator
from inlineKeyBoards import main_kb, collection_output_kb

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Конфиги (можете переопределить через env)
PREFIX_URL = os.getenv("COLL_PREFIX_URL", "https://img.bricklink.com/ItemImage/MN/0")
MIN_HEIGHT = int(os.getenv("COLL_MIN_HEIGHT", "1050"))
COLS = int(os.getenv("COLL_COLUMNS", "5"))
MAX_CONN = int(os.getenv("CONCURRENT_BATCHES", "5"))

router = Router()


@router.callback_query(lambda cb: cb.data == "my_collection")
async def cb_my_collection(call: types.CallbackQuery):
    await call.answer()
    user_id = str(call.from_user.id)

    records = await list_user_figures(user_id)
    if not records:
        return await call.message.answer("Ваша коллекция пуста.", reply_markup=main_kb)

    await call.message.answer(
        "Как хотите управлять вашей коллекцией?",
        reply_markup=collection_output_kb()
    )


@router.callback_query(lambda cb: cb.data == "collection_clear")
async def cb_collection_clear(call: types.CallbackQuery):
    await call.answer()
    user_id = str(call.from_user.id)

    # Очищаем коллекцию через API
    await clear_user_collection(user_id)

    await call.message.answer(
        "Ваша коллекция успешно очищена!", reply_markup=main_kb
    )


@router.callback_query(lambda cb: cb.data == "collection_tierlist")
async def cb_collection_tierlist(call: types.CallbackQuery):
    await call.answer()
    user_id = str(call.from_user.id)

    # 1) Получаем записи
    records = await list_user_figures(user_id)
    logger.info(f"[TIER] fetched {len(records) if records else 0} records for user {user_id}")

    if not records:
        return await call.message.answer(
            "Ваша коллекция пуста.", reply_markup=main_kb
        )

    # 2) Преобразуем в dict (если объекты с .dict)
    records_dicts = [
        rec.dict() if hasattr(rec, 'dict') else rec
        for rec in records
    ]
    logger.debug(f"[TIER] sample record: {records_dicts[0] if records_dicts else None}")

    # 3) Фильтрация (здесь keyword пустой — возвращает всё)
    df = StarWarsCollageGenerator.filter_by_keyword(
        data=records_dicts,
        name_key='name',
        keyword=''
    )
    logger.info(f"[TIER] after filter: {len(df)} rows")

    if len(df) == 0:
        return await call.message.answer("После фильтрации нет элементов.", reply_markup=main_kb)

    # 4) Асинхронное скачивание и подготовка изображений
    try:
        raw = await StarWarsCollageGenerator.fetch_and_prepare_images_async(
            records=df,
            id_key='bricklink_id',
            prefix_url=PREFIX_URL,
            min_height=MIN_HEIGHT,
            font_path='arial.ttf',
            font_size=90,
            max_connections=MAX_CONN,
            timeout=15
        )
        logger.info(f"[TIER] fetched {len(raw)} images")
    except Exception as e:
        logger.exception(f"[TIER] ERROR in fetch_and_prepare_images_async: {e}")
        return await call.message.answer(
            "Ошибка при загрузке изображений. Попробуйте позже.", reply_markup=main_kb
        )

    if not raw:
        logger.warning("[TIER] no images after fetch, aborting")
        return await call.message.answer(
            "Не удалось подготовить изображения.", reply_markup=main_kb
        )

    # 5) Собираем коллаж — используем асинхронную обёртку (с записью в temp file)
    # создаём временный файл
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tmp_path = tf.name

        await StarWarsCollageGenerator.create_collage_async(
            images=raw,
            output_path=tmp_path,
            columns=COLS,
            title=None,
            font_path='arial.ttf',
            font_size=90
        )
        logger.info(f"[TIER] collage created at {tmp_path}")

    except Exception as e:
        logger.exception(f"[TIER] ERROR creating collage: {e}")
        # try cleanup
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return await call.message.answer(
            "Ошибка при сборке коллажа.", reply_markup=main_kb
        )

    # 6) Отправляем файл и удаляем временный файл
    try:
        with open(tmp_path, 'rb') as f:
            document = BufferedInputFile(f.read(), filename="collection.png")

        await call.bot.send_document(
            chat_id=call.from_user.id,
            document=document,
            caption="Вот ваша коллекция в виде тир-листа!",
            reply_markup=main_kb
        )
        logger.info("[TIER] sent collage")
    except Exception as e:
        logger.exception(f"[TIER] ERROR sending collage: {e}")
        await call.message.answer(
            "Ошибка при отправке файла.", reply_markup=main_kb
        )
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@router.callback_query(lambda cb: cb.data == "collection_excel")
async def cb_collection_excel(call: types.CallbackQuery):
    await call.answer()
    user_id = str(call.from_user.id)

    records = await list_user_figures(user_id)
    if not records:
        return await call.message.answer("Коллекция пуста.", reply_markup=main_kb)
    # нормализуем записи в DataFrame (если объекты с dict)
    records_list = [rec.dict() if hasattr(rec, 'dict') else rec for rec in records]
    df = pd.DataFrame(records_list)

    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)

    document = BufferedInputFile(buf.read(), filename="collection.xlsx")
    await call.bot.send_document(
        chat_id=call.from_user.id,
        document=document,
        caption="Вот ваша коллекция в Excel-формате.", reply_markup=main_kb
    )
