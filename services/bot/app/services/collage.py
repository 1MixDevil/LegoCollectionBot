# async_collage.py
import logging
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import httpx
import asyncio
import os

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class StarWarsCollageGenerator:
    @staticmethod
    def filter_by_keyword(
        data: list | pd.DataFrame,
        name_key: str,
        keyword: str
    ) -> pd.DataFrame:
        """
        Sync: фильтрация списка/DataFrame по ключевым словам (оставил sync — дешёвая операция).
        """
        logger.info(f"Filtering {len(data)} records by keyword '{keyword}' on key '{name_key}'")
        df = pd.DataFrame(data)
        words = keyword.lower().split()

        def contains_all(text: str) -> bool:
            text = str(text).lower()
            return all(w in text for w in words)

        filtered = df[df[name_key].apply(contains_all)]
        logger.info(f"Filtered down to {len(filtered)} records")
        return filtered

    @staticmethod
    def load_font(font_path: str, font_size: int):
        """
        Load a TrueType font from candidates or fallback to default.
        """
        logger.info(f"Loading font '{font_path}' size {font_size}")
        font_candidates = [
            font_path,
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
        ]
        for fp in font_candidates:
            try:
                font = ImageFont.truetype(fp, font_size)
                logger.info(f"Loaded font '{fp}'")
                return font
            except Exception:
                logger.debug(f"Font path '{fp}' not found or can't be loaded, trying next")
        logger.info("Falling back to default font")
        return ImageFont.load_default()

    @staticmethod
    def _prepare_image_from_bytes(content: bytes, id_val: str, min_height: int, id_font):
        """
        CPU-bound sync helper to open/process image and draw text.
        Will be run in a thread via asyncio.to_thread.
        """
        try:
            img = Image.open(BytesIO(content)).convert("RGBA")
            # preserve aspect ratio
            new_h = min_height
            new_w = int(new_h * (img.width / img.height)) if img.height else new_h
            img = img.resize((new_w, new_h))

            pad_top, pad_bottom = 150, 150
            canvas = Image.new('RGB', (new_w, new_h + pad_top + pad_bottom), 'white')
            # paste preserving alpha
            if img.mode in ("RGBA", "LA"):
                canvas.paste(img.convert("RGBA"), (0, pad_top), img.convert("RGBA"))
            else:
                canvas.paste(img, (0, pad_top))

            draw = ImageDraw.Draw(canvas)
            draw.text((10, 10), id_val, font=id_font, fill='black')

            return (canvas, id_font)
        except Exception as e:
            logger.exception(f"Error preparing image for {id_val}: {e}")
            return None

    @classmethod
    async def fetch_and_prepare_images_async(
        cls,
        records: pd.DataFrame | list,
        id_key: str,
        prefix_url: str,
        min_height: int,
        font_path: str = 'arial.ttf',
        font_size: int = 90,
        user_agent: str = 'Mozilla/5.0',
        max_connections: int = 10,
        timeout: int = 15
    ) -> list:
        """
        Async: скачивает изображения параллельно (с ограниченной конкуренцией),
        затем обрабатывает каждое изображение в потоке (asyncio.to_thread).
        Возвращает list[(PIL.Image, ImageFont), ...]
        """
        logger.info(f"Starting async fetch for {len(records)} records (max_conn={max_connections})")
        # records may be DataFrame or list of dicts
        if isinstance(records, pd.DataFrame):
            rows = list(records.to_dict(orient='records'))
        else:
            rows = list(records)

        headers = {'User-Agent': user_agent}
        prefix = prefix_url.rstrip('/')
        id_font = cls.load_font(font_path, font_size)

        results = []
        semaphore = asyncio.Semaphore(max_connections)

        async def fetch_one(row):
            id_val = str(row.get(id_key) if isinstance(row, dict) else getattr(row, id_key, ''))
            url = f"{prefix}/{id_val}.png"
            logger.debug(f"Fetching {url}")
            try:
                async with semaphore:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        r = await client.get(url, headers=headers)
                        r.raise_for_status()
                        content = r.content
                # process in thread
                prepared = await asyncio.to_thread(cls._prepare_image_from_bytes, content, id_val, min_height, id_font)
                if prepared:
                    logger.debug(f"Prepared image for ID {id_val}")
                    return prepared
                else:
                    logger.warning(f"Processing failed for {id_val}")
                    return None
            except Exception as e:
                logger.debug(f"Failed to fetch/process {url}: {e}")
                return None

        # create tasks
        tasks = [asyncio.create_task(fetch_one(r)) for r in rows]
        # gather with no fail-fast (exceptions handled inside)
        completed = await asyncio.gather(*tasks, return_exceptions=False)
        # filter None
        prepared_items = [it for it in completed if it]
        logger.info(f"Prepared {len(prepared_items)} images out of {len(rows)} records")
        return prepared_items

    @staticmethod
    def _create_collage_impl(
        images: list,
        output_path: str,
        columns: int = 5,
        max_images: int = None,
        title: str = None,
        font_path: str = 'arial.ttf',
        font_size: int = 90
    ) -> None:
        """
        Sync implementation that assembles and saves collage (CPU-bound) —
        intended to be called in a thread.
        """
        count = len(images)
        if count == 0:
            logger.warning("No images to assemble into collage.")
            return

        items = images[:max_images] if max_images else images
        imgs, _ = zip(*items)

        w = max(im.width for im in imgs)
        h = max(im.height for im in imgs)
        rows = (len(items) + columns - 1) // columns

        title_padding = 0
        if title:
            title_font = StarWarsCollageGenerator.load_font(font_path, int(font_size * 1.5))
            dummy = Image.new('RGB', (1, 1))
            draw = ImageDraw.Draw(dummy)
            bbox = draw.textbbox((0, 0), title, font=title_font)
            text_height = bbox[3] - bbox[1]
            title_padding = text_height + 20
            logger.info(f"Adding title '{title}' with padding {title_padding}")

        collage = Image.new('RGB', (w * columns, h * rows + title_padding), 'white')

        if title:
            draw = ImageDraw.Draw(collage)
            x = (collage.width - (bbox[2] - bbox[0])) // 2
            y = 10
            draw.text((x, y), title, font=title_font, fill='black')

        logger.info(f"Creating collage grid {rows}x{columns}, size {collage.size}")
        offset_y = title_padding
        for idx, im in enumerate(imgs):
            x = (idx % columns) * w
            y = (idx // columns) * h + offset_y
            collage.paste(im, (x, y))

        # Ensure dir exists
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        collage.save(output_path)
        logger.info(f"Collage saved to {output_path}")

    @classmethod
    async def create_collage_async(
        cls,
        images: list,
        output_path: str,
        columns: int = 5,
        max_images: int = None,
        title: str = None,
        font_path: str = 'arial.ttf',
        font_size: int = 90
    ) -> None:
        """
        Async wrapper around _create_collage_impl — runs in thread to avoid blocking loop.
        """
        await asyncio.to_thread(
            cls._create_collage_impl,
            images, output_path, columns, max_images, title, font_path, font_size
        )

    @classmethod
    async def generate_from_list_async(
        cls,
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
        max_images: int = None,
        title: str = None,
        max_connections: int = 10
    ) -> None:
        """
        High-level async helper: фильтрует, скачивает и собирает коллаж.
        """
        df = cls.filter_by_keyword(data, name_key, keyword)
        items = await cls.fetch_and_prepare_images_async(
            records=df,
            id_key=id_key,
            prefix_url=prefix_url,
            min_height=min_height,
            font_path=font_path,
            font_size=font_size,
            max_connections=max_connections
        )
        if not items:
            logger.warning("No images prepared, skipping collage creation")
            return
        await cls.create_collage_async(
            images=items,
            output_path=output_path,
            columns=columns,
            max_images=max_images,
            title=title,
            font_path=font_path,
            font_size=font_size
        )
