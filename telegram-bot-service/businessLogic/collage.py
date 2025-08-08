import logging
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO

# Настройка логирования
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

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
            except IOError:
                logger.warning(f"Font path '{fp}' not found, trying next")
        logger.info("Falling back to default font")
        return ImageFont.load_default()

    @staticmethod
    def fetch_and_prepare_images(
        records: pd.DataFrame,
        id_key: str,
        prefix_url: str,
        min_height: int,
        font_path: str = 'arial.ttf',
        font_size: int = 90,
        user_agent: str = 'Mozilla/5.0'
    ) -> list:
        """
        Download images, resize, add padding and draw ID text at top.
        Returns list of tuples (image, font) where font is used for IDs.
        """
        logger.info(f"Starting image fetch for {len(records)} records")
        headers = {'User-Agent': user_agent}
        items = []

        id_font = StarWarsCollageGenerator.load_font(font_path, font_size)
        prefix = prefix_url.rstrip('/')

        for idx, row in records.iterrows():
            id_val = str(row[id_key])
            url = f"{prefix}/{id_val}.png"
            logger.debug(f"Fetching image {idx}: {url}")
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                continue

            try:
                img = Image.open(BytesIO(resp.content))
                new_h = min_height
                new_w = int(new_h * (img.width / img.height))
                img = img.resize((new_w, new_h))

                pad_top, pad_bottom = 150, 150
                canvas = Image.new('RGB', (new_w, new_h + pad_top + pad_bottom), 'white')
                canvas.paste(img, (0, pad_top))

                draw = ImageDraw.Draw(canvas)
                draw.text((10, 10), id_val, font=id_font, fill='black')

                items.append((canvas, id_font))
                logger.debug(f"Prepared image for ID {id_val}")
            except Exception as e:
                logger.error(f"Error processing image {id_val}: {e}")

        logger.info(f"Prepared {len(items)} images out of {len(records)} records")
        return items

    @staticmethod
    def create_collage(
        images: list,
        output_path: str,
        columns: int = 5,
        max_images: int = None,
        title: str = None,
        font_path: str = 'arial.ttf',
        font_size: int = 90
    ) -> None:
        """
        Assemble and save a collage from a list of (image, font) tuples.
        """
        count = len(images)
        if count == 0:
            logger.warning("No images to assemble into collage.")
            return

        items = images[:max_images] if max_images else images
        imgs, _ = zip(*items)

        w = max(im.width for im in imgs)
        h = max(im.height for im in imgs)
        rows = (count + columns - 1) // columns

        title_padding = 0
        if title:
            title_font = StarWarsCollageGenerator.load_font(font_path, int(font_size * 1.5))
            # measure title
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

        collage.save(output_path)
        logger.info(f"Collage saved to {output_path}")

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
        max_images: int = None,
        title: str = None
    ) -> None:
        df = StarWarsCollageGenerator.filter_by_keyword(data, name_key, keyword)
        items = StarWarsCollageGenerator.fetch_and_prepare_images(
            records=df,
            id_key=id_key,
            prefix_url=prefix_url,
            min_height=min_height,
            font_path=font_path,
            font_size=font_size
        )
        StarWarsCollageGenerator.create_collage(
            images=items,
            output_path=output_path,
            columns=columns,
            max_images=max_images,
            title=title,
            font_path=font_path,
            font_size=font_size
        )
