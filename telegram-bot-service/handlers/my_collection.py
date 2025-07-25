# handlers/my_collection.py
from aiogram import Router, types
from HttpRequests import list_user_figures
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

    # Сохраним записи во временное хранилище (можно в FSM или базу, но пока просто повторим при выборе)
    await call.message.answer(
        "Как хотите экспортировать вашу коллекцию?",
        reply_markup=collection_output_kb()
    )


@router.callback_query(lambda cb: cb.data == "collection_tierlist")
async def cb_collection_tierlist(call: types.CallbackQuery):
    await call.answer()
    user_id = str(call.from_user.id)

    records = await list_user_figures(user_id)
    if not records:
        return await call.message.answer("Ваша коллекция пуста.", reply_markup=main_kb)

    images = StarWarsCollageGenerator.fetch_and_prepare_images(
        records=StarWarsCollageGenerator.filter_by_keyword(records, name_key='name', keyword=''),
        id_key='bricklink_id',
        prefix_url='https://img.bricklink.com/ItemImage/MN/0/',
        min_height=1050,
        font_path='arial.ttf',
        font_size=90,
    )

    if not images:
        return await call.message.answer("Не удалось подготовить изображения.", reply_markup=main_kb)

    def build_collage_image(img_list, columns=5):
        count = len(img_list)
        rows = (count + columns - 1) // columns
        w = max(im.width for im in img_list)
        h = max(im.height for im in img_list)
        collage = Image.new('RGB', (w * columns, h * rows), (255, 255, 255))
        for idx, im in enumerate(img_list):
            x = (idx % columns) * w
            y = (idx // columns) * h
            collage.paste(im, (x, y))
        return collage

    collage = build_collage_image(images)
    buf = BytesIO()
    collage.save(buf, format='PNG')
    buf.seek(0)

    document = BufferedInputFile(buf.read(), filename="my_collection.png")
    await call.bot.send_document(
        chat_id=call.from_user.id,
        document=document,
        caption="Вот ваша коллекция в виде тир-листа!",
        reply_markup=main_kb
    )


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
        caption="Вот ваша коллекция в Excel-формате.",
        reply_markup=main_kb
    )
