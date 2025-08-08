from aiogram import Router, types
from HttpRequests import list_user_figures, clear_user_collection
from businessLogic.collage import StarWarsCollageGenerator
from inlineKeyBoards import main_kb, collection_output_kb
from aiogram.types import BufferedInputFile
from PIL import Image
from io import BytesIO
import pandas as pd

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
    print(f"[TIER] fetched {len(records)} records for user {user_id}")

    if not records:
        return await call.message.answer(
            "Ваша коллекция пуста.", reply_markup=main_kb
        )

    # 2) Преобразуем в dict
    records_dicts = [
        rec.dict() if hasattr(rec, 'dict') else rec
        for rec in records
    ]
    print(f"[TIER] sample record: {records_dicts[0]}")

    # 3) Фильтрация
    df = StarWarsCollageGenerator.filter_by_keyword(
        data=records_dicts,
        name_key='name',
        keyword=''
    )
    print(f"[TIER] after filter: {len(df)} rows")

    # 4) Загрузка изображений c обработкой ошибок
    try:
        raw = StarWarsCollageGenerator.fetch_and_prepare_images(
            records=df,
            id_key='bricklink_id',
            prefix_url='https://img.bricklink.com/ItemImage/MN/0',
            min_height=1050,
            font_path='arial.ttf',
            font_size=90,
        )
        print(f"[TIER] fetched {len(raw)} images")
    except Exception as e:
        # Логируем полную трассировку
        import traceback
        tb = traceback.format_exc()
        print(f"[TIER] ERROR in fetch_and_prepare_images: {e}\n{tb}")
        return await call.message.answer(
            "Ошибка при загрузке изображений. Попробуйте позже.", reply_markup=main_kb
        )

    if not raw:
        print("[TIER] no images after fetch, aborting")
        return await call.message.answer(
            "Не удалось подготовить изображения.", reply_markup=main_kb
        )

    # 5) Собираем коллаж
    images = [img for img, _ in raw]
    try:
        w = max(im.width for im in images)
        h = max(im.height for im in images)
        cols = 5
        rows = (len(images) + cols - 1) // cols
        collage = Image.new('RGB', (w * cols, h * rows), 'white')
        for idx, im in enumerate(images):
            x = (idx % cols) * w
            y = (idx // cols) * h
            collage.paste(im, (x, y))
        print(f"[TIER] collage created, size: {collage.size}")
    except Exception as e:
        print(f"[TIER] ERROR building collage: {e}", exc_info=True)
        return await call.message.answer(
            "Ошибка при сборке коллажа.", reply_markup=main_kb
        )

    # 6) Отправляем файл
    buf = BytesIO()
    collage.save(buf, format='PNG')
    buf.seek(0)
    document = BufferedInputFile(buf.read(), filename="collection.png")

    await call.bot.send_document(
        chat_id=call.from_user.id,
        document=document,
        caption="Вот ваша коллекция в виде тир-листа!",
        reply_markup=main_kb
    )
    print("[TIER] sent collage")


@router.callback_query(lambda cb: cb.data == "collection_excel")
async def cb_collection_excel(call: types.CallbackQuery):
    await call.answer()
    user_id = str(call.from_user.id)

    records = await list_user_figures(user_id)
    if not records:
        return await call.message.answer("Коллекция пуста.", reply_markup=main_kb)

    df = pd.DataFrame(records)

    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)

    document = BufferedInputFile(buf.read(), filename="collection.xlsx")
    await call.bot.send_document(
        chat_id=call.from_user.id,
        document=document,
        caption="Вот ваша коллекция в Excel-формате.", reply_markup=main_kb
    )
