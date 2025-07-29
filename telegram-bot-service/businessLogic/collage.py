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
    def load_font(font_path: str, font_size: int):
        """
        Load a TrueType font from candidates or fallback to default.
        """
        font_candidates = [
            font_path,
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
        ]
        for fp in font_candidates:
            try:
                return ImageFont.truetype(fp, font_size)
            except IOError:
                continue
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
        Download images from BrickLink, resize, add padding and draw ID text at top.
        Returns list of tuples (image, font) where font is used for IDs.
        """
        headers = {'User-Agent': user_agent}
        items = []

        # Load font for IDs
        id_font = StarWarsCollageGenerator.load_font(font_path, font_size)
        prefix = prefix_url.rstrip('/')

        for _, row in records.iterrows():
            id_val = str(row[id_key])
            url = f"{prefix}/{id_val}.png"
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                continue

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
        Assemble and save a collage from a list of (image, font) tuples passed in `images`.
        Optionally draw a centered title at the very top using 1.5× the ID font size,
        and shift the entire image grid below it.
        """
        if not images:
            print("No images to assemble.")
            return

        items = images[:max_images] if max_images else images
        imgs, fonts = zip(*items)

        count = len(imgs)
        rows = (count + columns - 1) // columns
        w = max(im.width for im in imgs)
        h = max(im.height for im in imgs)

        # Prepare title font at 1.5× size
        title_font = None
        title_margin = 10
        text_width = text_height = title_padding = 0
        if title:
            title_font_size = int(font_size * 1.5)
            title_font = StarWarsCollageGenerator.load_font(font_path, title_font_size)
            # measure title
            dummy_img = Image.new('RGB', (1, 1))
            dummy_draw = ImageDraw.Draw(dummy_img)
            bbox = dummy_draw.textbbox((0, 0), title, font=title_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            title_padding = title_margin + text_height + title_margin

        # Create canvas with space for title
        collage = Image.new('RGB', (w * columns, h * rows + title_padding), 'white')

        # Draw title at very top
        if title and title_font:
            draw = ImageDraw.Draw(collage)
            x = (collage.width - text_width) // 2
            y = title_margin
            draw.text((x, y), title, font=title_font, fill='black')

        # Paste images shifted below title
        offset_y = title_padding
        for idx, im in enumerate(imgs):
            x = (idx % columns) * w
            y = (idx // columns) * h + offset_y
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
        max_images: int = None,
        title: str = None
    ) -> None:
        """
        Full pipeline: filter, download, prepare and assemble collage.
        Optional title appears centered at the very top of the collage in 1.5× font size.
        """
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
