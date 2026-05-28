"""Сборка коллажей: потоковая склейка по рядам (низкое потребление RAM)."""

from __future__ import annotations

import asyncio
import gc
import logging
import os
from io import BytesIO

import httpx
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

COLLAGE_JPEG_QUALITY = int(os.getenv("COLLAGE_JPEG_QUALITY", "82"))
COLLAGE_PNG_COMPRESS = int(os.getenv("COLLAGE_PNG_COMPRESS", "6"))
COLLAGE_CELL_PAD = int(os.getenv("COLLAGE_CELL_PAD", "80"))


class StarWarsCollageGenerator:
    @staticmethod
    def save_collage_image(collage: Image.Image, output_path: str) -> str:
        path_lower = output_path.lower()
        if path_lower.endswith((".jpg", ".jpeg")):
            out = output_path.rsplit(".", 1)[0] + ".jpg"
            rgb = collage.convert("RGB")
            rgb.save(
                out,
                format="JPEG",
                quality=COLLAGE_JPEG_QUALITY,
                optimize=True,
            )
            rgb.close()
            return out
        collage.save(
            output_path,
            format="PNG",
            optimize=True,
            compress_level=min(9, max(0, COLLAGE_PNG_COMPRESS)),
        )
        return output_path

    @staticmethod
    def filter_by_keyword(
        data: list | pd.DataFrame,
        name_key: str,
        keyword: str,
    ) -> pd.DataFrame:
        df = pd.DataFrame(data)
        words = keyword.lower().split()

        def contains_all(text: str) -> bool:
            text = str(text).lower()
            return all(w in text for w in words)

        return df[df[name_key].apply(contains_all)]

    @staticmethod
    def load_font(font_path: str, font_size: int):
        font_candidates = [
            font_path,
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for fp in font_candidates:
            try:
                return ImageFont.truetype(fp, font_size)
            except Exception:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _draw_owned_mark(
        draw: ImageDraw.ImageDraw, width: int, height: int, pad_top: int
    ) -> None:
        margin = max(16, width // 25)
        y0 = pad_top + margin
        y1 = height - margin
        x0, x1 = margin, width - margin
        stroke = max(10, width // 28)
        red = (220, 25, 25)
        dark = (120, 10, 10)
        for line in ([(x0, y0), (x1, y1)], [(x0, y1), (x1, y0)]):
            draw.line(line, fill=dark, width=stroke + 4)
            draw.line(line, fill=red, width=stroke)

    @staticmethod
    def _prepare_image_from_bytes(
        content: bytes,
        id_val: str,
        min_height: int,
        id_font,
        owned_ids: frozenset[str] | None = None,
    ) -> Image.Image | None:
        try:
            img = Image.open(BytesIO(content)).convert("RGBA")
            new_h = min_height
            new_w = int(new_h * (img.width / img.height)) if img.height else new_h
            img = img.resize((new_w, new_h))

            pad_top = pad_bottom = COLLAGE_CELL_PAD
            canvas = Image.new("RGB", (new_w, new_h + pad_top + pad_bottom), "white")
            canvas.paste(img, (0, pad_top), img)
            img.close()

            draw = ImageDraw.Draw(canvas)
            draw.text((10, 10), id_val, font=id_font, fill="black")
            if owned_ids and id_val.lower() in owned_ids:
                StarWarsCollageGenerator._draw_owned_mark(
                    draw, canvas.width, canvas.height, pad_top
                )
            return canvas
        except Exception:
            logger.debug("prepare image failed for %s", id_val, exc_info=True)
            return None

    @staticmethod
    def _make_row_strip(cells: list[Image.Image], columns: int) -> Image.Image | None:
        if not cells:
            return None
        w = max(im.width for im in cells)
        h = max(im.height for im in cells)
        strip = Image.new("RGB", (w * columns, h), "white")
        for i, im in enumerate(cells):
            y_off = (h - im.height) // 2
            strip.paste(im, (i * w, y_off))
            im.close()
        return strip

    @staticmethod
    def _title_padding(title: str | None, font_path: str, font_size: int) -> tuple[int, object | None, object | None]:
        if not title:
            return 0, None, None
        title_font = StarWarsCollageGenerator.load_font(font_path, int(font_size * 1.5))
        dummy = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), title, font=title_font)
        dummy.close()
        text_height = bbox[3] - bbox[1]
        return text_height + 80, title_font, bbox

    @staticmethod
    def _append_row(
        collage: Image.Image | None,
        row_strip: Image.Image,
        *,
        columns: int,
        title: str | None,
        title_padding: int,
        title_font,
        title_bbox,
        is_first: bool,
    ) -> Image.Image:
        if collage is None:
            width = max(row_strip.width, columns * 100)
            height = title_padding + row_strip.height
            collage = Image.new("RGB", (width, height), "white")
            if title and title_font and title_bbox:
                draw = ImageDraw.Draw(collage)
                x = (collage.width - (title_bbox[2] - title_bbox[0])) // 2
                draw.text((x, 10), title, font=title_font, fill="black")
            collage.paste(row_strip, (0, title_padding))
            row_strip.close()
            return collage

        new_w = max(collage.width, row_strip.width)
        new_h = collage.height + row_strip.height
        merged = Image.new("RGB", (new_w, new_h), "white")
        merged.paste(collage, (0, 0))
        merged.paste(row_strip, (0, collage.height))
        collage.close()
        row_strip.close()
        return merged

    @classmethod
    async def build_collage_to_file(
        cls,
        records: list,
        output_path: str,
        *,
        id_key: str = "bricklink_id",
        prefix_url: str,
        min_height: int,
        columns: int = 5,
        title: str | None = None,
        font_path: str = "arial.ttf",
        font_size: int = 90,
        max_connections: int = 3,
        owned_ids: frozenset[str] | None = None,
    ) -> int:
        """
        Скачивает и склеивает по одному ряду (columns ячеек).
        В RAM одновременно — не больше одного ряда + текущий коллаж.
        """
        if isinstance(records, pd.DataFrame):
            rows = list(records.to_dict(orient="records"))
        else:
            rows = list(records)
        if not rows:
            return 0

        id_font = await asyncio.to_thread(cls.load_font, font_path, font_size)
        title_padding, title_font, title_bbox = await asyncio.to_thread(
            cls._title_padding, title, font_path, font_size
        )

        prefix = prefix_url.rstrip("/")
        headers = {"User-Agent": "Mozilla/5.0"}
        semaphore = asyncio.Semaphore(max_connections)
        collage: Image.Image | None = None
        placed = 0
        row_index = 0

        async with httpx.AsyncClient(timeout=20.0) as client:

            async def fetch_cell(row: dict) -> Image.Image | None:
                id_val = str(row.get(id_key, "")).strip()
                if not id_val:
                    return None
                url = f"{prefix}/{id_val}.png"
                try:
                    async with semaphore:
                        resp = await client.get(url, headers=headers)
                        resp.raise_for_status()
                        content = resp.content
                    return await asyncio.to_thread(
                        cls._prepare_image_from_bytes,
                        content,
                        id_val,
                        min_height,
                        id_font,
                        owned_ids,
                    )
                except Exception:
                    logger.debug("fetch failed %s", url, exc_info=True)
                    return None

            for start in range(0, len(rows), columns):
                chunk = rows[start : start + columns]
                tasks = [asyncio.create_task(fetch_cell(r)) for r in chunk]
                cells = [c for c in await asyncio.gather(*tasks) if c is not None]
                if not cells:
                    continue

                row_strip = await asyncio.to_thread(
                    cls._make_row_strip, cells, columns
                )
                if row_strip is None:
                    continue

                is_first = row_index == 0
                collage = await asyncio.to_thread(
                    cls._append_row,
                    collage,
                    row_strip,
                    columns=columns,
                    title=title if is_first else None,
                    title_padding=title_padding,
                    title_font=title_font,
                    title_bbox=title_bbox,
                    is_first=is_first,
                )
                placed += len(cells)
                row_index += 1
                gc.collect()

        if collage is None:
            return 0

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        size = collage.size
        saved_path = await asyncio.to_thread(
            cls.save_collage_image, collage, output_path
        )
        collage.close()
        gc.collect()
        logger.info(
            "Streaming collage saved: %s (%s cells, size %sx%s)",
            saved_path,
            placed,
            size[0],
            size[1],
        )
        return placed

    # --- совместимость со старыми вызовами ---

    @classmethod
    async def fetch_and_prepare_images_async(cls, *args, **kwargs) -> list:
        logger.warning("fetch_and_prepare_images_async is deprecated; use build_collage_to_file")
        records = kwargs.get("records") or (args[0] if args else [])
        min_height = kwargs.get("min_height", 900)
        prefix_url = kwargs.get("prefix_url", "")
        id_key = kwargs.get("id_key", "bricklink_id")
        owned_ids = kwargs.get("owned_ids")
        max_connections = kwargs.get("max_connections", 3)

        rows = (
            list(records.to_dict(orient="records"))
            if isinstance(records, pd.DataFrame)
            else list(records)
        )
        id_font = cls.load_font(kwargs.get("font_path", "arial.ttf"), kwargs.get("font_size", 90))
        prefix = prefix_url.rstrip("/")
        headers = {"User-Agent": "Mozilla/5.0"}
        semaphore = asyncio.Semaphore(max_connections)
        out = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            for row in rows[:5]:
                id_val = str(row.get(id_key, ""))
                url = f"{prefix}/{id_val}.png"
                async with semaphore:
                    r = await client.get(url, headers=headers)
                    r.raise_for_status()
                    im = await asyncio.to_thread(
                        cls._prepare_image_from_bytes,
                        r.content,
                        id_val,
                        min_height,
                        id_font,
                        owned_ids,
                    )
                    if im:
                        out.append((im, id_font))
        return out

    @classmethod
    async def create_collage_async(cls, images: list, output_path: str, **kwargs) -> None:
        await asyncio.to_thread(
            cls._create_collage_impl_legacy,
            images,
            output_path,
            kwargs.get("columns", 5),
            kwargs.get("title"),
            kwargs.get("font_path", "arial.ttf"),
            kwargs.get("font_size", 90),
        )

    @staticmethod
    def _create_collage_impl_legacy(
        images: list,
        output_path: str,
        columns: int,
        title: str | None,
        font_path: str,
        font_size: int,
    ) -> None:
        if not images:
            return
        items = images
        imgs = [it[0] if isinstance(it, tuple) else it for it in items]
        w = max(im.width for im in imgs)
        h = max(im.height for im in imgs)
        rows_n = (len(imgs) + columns - 1) // columns
        title_padding, title_font, bbox = StarWarsCollageGenerator._title_padding(
            title, font_path, font_size
        )
        collage = Image.new("RGB", (w * columns, h * rows_n + title_padding), "white")
        if title and title_font and bbox:
            draw = ImageDraw.Draw(collage)
            x = (collage.width - (bbox[2] - bbox[0])) // 2
            draw.text((x, 10), title, font=title_font, fill="black")
        for idx, im in enumerate(imgs):
            collage.paste(im, ((idx % columns) * w, (idx // columns) * h + title_padding))
            im.close()
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        StarWarsCollageGenerator.save_collage_image(collage, output_path)
        collage.close()

    @classmethod
    async def generate_from_list_async(
        cls,
        data: list,
        keyword: str,
        name_key: str,
        id_key: str,
        prefix_url: str,
        output_path: str,
        min_height: int = 900,
        **kwargs,
    ) -> None:
        df = cls.filter_by_keyword(data, name_key, keyword)
        await cls.build_collage_to_file(
            list(df.to_dict(orient="records")),
            output_path,
            id_key=id_key,
            prefix_url=prefix_url,
            min_height=min_height,
            columns=kwargs.get("columns", 5),
            title=kwargs.get("title"),
            max_connections=kwargs.get("max_connections", 3),
        )
