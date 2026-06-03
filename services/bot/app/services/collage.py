"""Сборка коллажей: единая сетка columns×rows (ровный прямоугольник)."""

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
COLLAGE_CELL_PAD = int(os.getenv("COLLAGE_CELL_PAD", "120"))
# Макс. сторона итогового коллажа (px) — защита от гигантских bitmap в RAM
COLLAGE_MAX_DIMENSION = int(os.getenv("COLLAGE_MAX_DIMENSION", "10000"))


class StarWarsCollageGenerator:
    @staticmethod
    def save_collage_image(collage: Image.Image, output_path: str) -> str:
        path_lower = output_path.lower()
        if path_lower.endswith((".jpg", ".jpeg")):
            out = output_path.rsplit(".", 1)[0] + ".jpg"
            if collage.mode == "RGB":
                collage.save(
                    out,
                    format="JPEG",
                    quality=COLLAGE_JPEG_QUALITY,
                    optimize=True,
                )
            else:
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
    def _downscale_if_needed(img: Image.Image) -> Image.Image:
        w, h = img.size
        longest = max(w, h)
        if longest <= COLLAGE_MAX_DIMENSION:
            return img
        scale = COLLAGE_MAX_DIMENSION / longest
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        img.close()
        logger.info("Collage downscaled %dx%d -> %dx%d", w, h, nw, nh)
        return resized

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
        display_text: str,
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
            draw.text((10, 10), display_text, font=id_font, fill="black")
            if owned_ids and id_val.lower() in owned_ids:
                StarWarsCollageGenerator._draw_owned_mark(
                    draw, canvas.width, canvas.height, pad_top
                )
            return canvas
        except Exception:
            logger.debug("prepare image failed for %s", id_val, exc_info=True)
            return None

    @classmethod
    async def fetch_and_prepare_images_async(
        cls,
        records: pd.DataFrame | list,
        id_key: str,
        prefix_url: str,
        min_height: int,
        font_path: str = "arial.ttf",
        font_size: int = 90,
        user_agent: str = "Mozilla/5.0",
        max_connections: int = 10,
        timeout: int = 15,
        owned_ids: frozenset[str] | None = None,
    ) -> list[Image.Image]:
        """Скачивает и готовит ячейки (одинаковая сетка собирается в _create_collage_impl)."""
        if isinstance(records, pd.DataFrame):
            rows = list(records.to_dict(orient="records"))
        else:
            rows = list(records)

        prefix = prefix_url.rstrip("/")
        headers = {"User-Agent": user_agent}
        id_font = cls.load_font(font_path, font_size)
        semaphore = asyncio.Semaphore(max_connections)

        async with httpx.AsyncClient(timeout=timeout) as client:

            async def fetch_one(row: dict) -> Image.Image | None:
                id_val = str(row.get(id_key, "")).strip()
                if not id_val:
                    return None
                display_text = str(row.get("display_id") or id_val).strip()
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
                        display_text,
                        min_height,
                        id_font,
                        owned_ids,
                    )
                except Exception:
                    logger.debug("fetch failed %s", url, exc_info=True)
                    return None

            tasks = [asyncio.create_task(fetch_one(r)) for r in rows]
            done = await asyncio.gather(*tasks)
        images = [im for im in done if im is not None]
        logger.info("Prepared %s images out of %s records", len(images), len(rows))
        return images

    @staticmethod
    def _create_collage_impl(
        images: list[Image.Image],
        output_path: str,
        columns: int = 5,
        title: str | None = None,
        font_path: str = "arial.ttf",
        font_size: int = 90,
    ) -> None:
        """Ровная сетка columns×rows: общие w×h для всех ячеек (как в оригинале)."""
        if not images:
            logger.warning("No images to assemble into collage.")
            return

        w = max(im.width for im in images)
        h = max(im.height for im in images)
        rows_n = (len(images) + columns - 1) // columns

        title_padding = 0
        title_font = None
        bbox = None
        if title:
            title_font = StarWarsCollageGenerator.load_font(
                font_path, int(font_size * 1.5)
            )
            dummy = Image.new("RGB", (1, 1))
            draw = ImageDraw.Draw(dummy)
            bbox = draw.textbbox((0, 0), title, font=title_font)
            text_height = bbox[3] - bbox[1]
            title_padding = text_height + 80
            dummy.close()

        collage = Image.new(
            "RGB", (w * columns, h * rows_n + title_padding), "white"
        )

        if title and title_font and bbox:
            draw = ImageDraw.Draw(collage)
            x = (collage.width - (bbox[2] - bbox[0])) // 2
            draw.text((x, 10), title, font=title_font, fill="black")

        logger.info(
            "Creating collage grid %sx%s, cell %sx%s, canvas %s",
            rows_n,
            columns,
            w,
            h,
            collage.size,
        )
        for idx, im in enumerate(images):
            x = (idx % columns) * w
            y = (idx // columns) * h + title_padding
            collage.paste(im, (x, y))
            im.close()

        collage = StarWarsCollageGenerator._downscale_if_needed(collage)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        saved = StarWarsCollageGenerator.save_collage_image(collage, output_path)
        collage.close()
        logger.info("Collage saved to %s", saved)

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
        """Скачивает ячейки и собирает ровную сетку (батч до ~50 в Celery — OK по RAM)."""
        images = await cls.fetch_and_prepare_images_async(
            records=records,
            id_key=id_key,
            prefix_url=prefix_url,
            min_height=min_height,
            font_path=font_path,
            font_size=font_size,
            max_connections=max_connections,
            owned_ids=owned_ids,
        )
        if not images:
            return 0

        await asyncio.to_thread(
            cls._create_collage_impl,
            images,
            output_path,
            columns,
            title,
            font_path,
            font_size,
        )
        gc.collect()
        return len(images)

    @classmethod
    async def create_collage_async(
        cls,
        images: list,
        output_path: str,
        columns: int = 5,
        title: str | None = None,
        font_path: str = "arial.ttf",
        font_size: int = 90,
    ) -> None:
        imgs = [it[0] if isinstance(it, tuple) else it for it in images]
        await asyncio.to_thread(
            cls._create_collage_impl,
            imgs,
            output_path,
            columns,
            title,
            font_path,
            font_size,
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
