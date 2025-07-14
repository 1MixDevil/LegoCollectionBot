# businessLogic/collage.py

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO


class StarWarsCollageGenerator:
    @staticmethod
    def filter_by_keyword(
        data: list,
        name_key: str,
        keyword: str
    ) -> pd.DataFrame:
        """
        Filter list of dicts where name_key contains all words from keyword.
        """
        df = pd.DataFrame(data)
        words = keyword.lower().split()

        def contains_all(text: str) -> bool:
            text = str(text).lower()
            return all(w in text for w in words)

        return df[df[name_key].apply(contains_all)]

    @staticmethod
    def fetch_and_prepare_images(
        records: pd.DataFrame,
        id_key: str,
        prefix_url: str,
        min_height: int,
        # ваш кастомный arial.ttf можно класть рядом с кодом
        font_path: str = 'arial.ttf',
        # базовый размер, можно корректировать
        font_size: int = 90,
        user_agent: str = 'Mozilla/5.0'
    ) -> list:
        """
        Download images from BrickLink, resize, add padding and draw ID text at top.
        """
        headers = {'User-Agent': user_agent}
        images = []

        # Попытка открытия первого доступного шрифта:
        font = None
        tried = []

        # Список кандидатов: ваш arial, DejaVu, Liberation
        font_candidates = [
            font_path,
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
        ]
        for fp in font_candidates:
            try:
                font = ImageFont.truetype(fp, font_size)
                print(f"Loaded font: {fp}")
                break
            except IOError:
                tried.append(fp)

        if font is None:
            print(f"Не удалось загрузить шрифты {tried}, используем дефолтный.")
            font = ImageFont.load_default()

        prefix = prefix_url.rstrip('/')

        for _, row in records.iterrows():
            id_val = str(row[id_key])
            url = f"{prefix}/{id_val}.png"
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                print(f"Skipping {id_val}: HTTP {resp.status_code}")
                continue

            # Открываем и масштабируем
            img = Image.open(BytesIO(resp.content))
            new_h = min_height
            new_w = int(new_h * (img.width / img.height))
            img = img.resize((new_w, new_h))

            # Добавляем отступы сверху/снизу
            pad_top, pad_bottom = 150, 150
            canvas = Image.new('RGB', (new_w, new_h + pad_top + pad_bottom), 'white')
            canvas.paste(img, (0, pad_top))

            # Рисуем ID в верхней части
            draw = ImageDraw.Draw(canvas)
            draw.text((10, 10), id_val, font=font, fill='black')

            images.append(canvas)

        return images

    @staticmethod
    def create_collage(
        images: list,
        output_path: str,
        columns: int = 5,
        max_images: int = None
    ) -> None:
        """
        Assemble and save a collage from a list of PIL.Image.
        """
        if not images:
            print("No images to assemble.")
            return

        imgs = images[:max_images] if max_images else images
        count = len(imgs)
        rows = (count + columns - 1) // columns
        w = max(im.width for im in imgs)
        h = max(im.height for im in imgs)

        collage = Image.new('RGB', (w * columns, h * rows), 'white')
        for idx, im in enumerate(imgs):
            x = (idx % columns) * w
            y = (idx // columns) * h
            collage.paste(im, (x, y))

        collage.save(output_path)
        print(f"Collage saved to {output_path}")

    @staticmethod
    def generate_from_list(
        data: list,
        keyword: str,
        name_key: str,
        id_key: str,
        prefix_url: str,
        output_path: str,
        min_height: int = 1050,
        font_path: str = 'arial.ttf',
        font_size: int = 90,
        columns: int = 5,
        max_images: int = None
    ) -> None:
        """
        Full pipeline: filter, download, prepare and assemble collage.
        """
        df = StarWarsCollageGenerator.filter_by_keyword(data, name_key, keyword)
        images = StarWarsCollageGenerator.fetch_and_prepare_images(
            records=df,
            id_key=id_key,
            prefix_url=prefix_url,
            min_height=min_height,
            font_path=font_path,
            font_size=font_size
        )
        StarWarsCollageGenerator.create_collage(images, output_path, columns, max_images)
