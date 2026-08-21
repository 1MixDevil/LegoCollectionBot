#!/usr/bin/env python3
"""Самодостаточная проверка коллажа с водяным знаком (только Pillow + httpx).

  python3 scripts/generate_test_collage.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

PREFIX_URL = "https://img.bricklink.com/ItemImage/MN/0"
MIN_HEIGHT = 800
CELL_PAD = 120
ROOT = Path(__file__).resolve().parents[1]


def load_font(size: int):
    for fp in (
        "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _resample_bicubic():
    return getattr(getattr(Image, "Resampling", Image), "BICUBIC", Image.BICUBIC)


def apply_watermark(collage: Image.Image, text: str) -> Image.Image:
    label = (text or "").strip()
    if not label:
        return collage

    w, h = collage.size
    font_size = max(28, min(w, h) // 14)
    font = load_font(font_size)
    fill = (90, 90, 90, 26)

    dummy = Image.new("RGBA", (1, 1))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), label, font=font)
    dummy.close()
    tw = max(1, bbox[2] - bbox[0])
    th = max(1, bbox[3] - bbox[1])

    pad = font_size
    tile = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((pad, pad), label, font=font, fill=fill)
    rotated = tile.rotate(28, expand=True, resample=_resample_bicubic())
    tile.close()

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rw, rh = rotated.size
    step_x = max(rw + font_size, int(rw * 1.35))
    step_y = max(rh + font_size, int(rh * 1.55))
    for y in range(-rh, h + rh, step_y):
        for x in range(-rw, w + rw, step_x):
            overlay.paste(rotated, (x, y), rotated)
    rotated.close()

    base = collage.convert("RGBA")
    merged = Image.alpha_composite(base, overlay)
    base.close()
    overlay.close()
    out = merged.convert("RGB")
    merged.close()
    collage.close()
    return out


def prepare_cell(content: bytes, fig_id: str, id_font) -> Image.Image:
    img = Image.open(BytesIO(content)).convert("RGBA")
    new_h = MIN_HEIGHT
    new_w = int(new_h * (img.width / img.height)) if img.height else new_h
    img = img.resize((new_w, new_h))
    canvas = Image.new("RGB", (new_w, new_h + CELL_PAD * 2), "white")
    canvas.paste(img, (0, CELL_PAD), img)
    img.close()
    ImageDraw.Draw(canvas).text((10, 10), fig_id, font=id_font, fill="black")
    return canvas


async def fetch_cells(ids: list[str]) -> list[Image.Image]:
    id_font = load_font(90)
    headers = {"User-Agent": "Mozilla/5.0 LegoCollectionBot-test"}
    prefix = PREFIX_URL.rstrip("/")
    images: list[Image.Image] = []
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        for fig_id in ids:
            url = f"{prefix}/{fig_id}.png"
            print(f"  fetch {url}")
            resp = await client.get(url)
            resp.raise_for_status()
            images.append(prepare_cell(resp.content, fig_id, id_font))
    return images


def assemble(images: list[Image.Image], columns: int, title: str, watermark: str) -> Image.Image:
    w = max(im.width for im in images)
    h = max(im.height for im in images)
    rows = (len(images) + columns - 1) // columns

    title_pad = 0
    title_font = None
    bbox = None
    if title:
        title_font = load_font(int(90 * 1.5))
        dummy = Image.new("RGB", (1, 1))
        bbox = ImageDraw.Draw(dummy).textbbox((0, 0), title, font=title_font)
        title_pad = (bbox[3] - bbox[1]) + 80
        dummy.close()

    collage = Image.new("RGB", (w * columns, h * rows + title_pad), "white")
    if title and title_font and bbox:
        x = (collage.width - (bbox[2] - bbox[0])) // 2
        ImageDraw.Draw(collage).text((x, 10), title, font=title_font, fill="black")

    for idx, im in enumerate(images):
        collage.paste(im, ((idx % columns) * w, (idx // columns) * h + title_pad))
        im.close()

    return apply_watermark(collage, watermark)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ids", nargs="+", default=["sw0001", "sw0002"])
    p.add_argument("--watermark", default="@test_test")
    p.add_argument("--title", default="Watermark test")
    p.add_argument(
        "--out",
        default=str(ROOT / "tmp" / "test_collage_watermark.jpg"),
    )
    args = p.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Building: ids={args.ids}, watermark={args.watermark!r}")
    images = await fetch_cells(args.ids)
    collage = assemble(images, columns=min(2, len(images)), title=args.title, watermark=args.watermark)
    collage.save(out, format="JPEG", quality=85, optimize=True)
    size = out.stat().st_size
    print(f"OK -> {out} ({size} bytes, {collage.size[0]}x{collage.size[1]})")
    collage.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
