#!/usr/bin/env python3
"""Render poster copy with a real local font without deforming glyphs."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def rgba(value, opacity=1.0):
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Invalid color: {value}")
    rgb = tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    return (*rgb, round(255 * opacity))


def px(value, extent):
    return round(value * extent) if isinstance(value, float) and 0 <= value <= 1 else round(value)


def render_block(canvas, font_path, block):
    width, height = canvas.size
    size = max(1, px(block["font_size"], height))
    font = ImageFont.truetype(str(font_path), size=size)
    color = rgba(block.get("color", "#111111"), block.get("opacity", 1.0))
    x = px(block["x"], width)
    y = px(block["y"], height)
    tracking = px(block.get("tracking", 0), width)
    rotations = block.get("char_rotations", [])
    offsets = block.get("char_y_offsets", [])
    positions = block.get("char_positions")
    if positions is not None and len(positions) != len(block["text"].replace("\n", "")):
        raise ValueError("char_positions must match the number of non-newline characters")
    position_index = 0

    for index, char in enumerate(block["text"]):
        if char == "\n":
            y += round(size * block.get("line_spacing", 1.25))
            x = px(block["x"], width)
            continue
        position = positions[position_index] if positions is not None else {}
        position_index += 1
        if positions is not None:
            x = px(position["x"], width)
            y = px(position["y"], height)
            size = max(1, px(position.get("font_size", block["font_size"]), height))
            font = ImageFont.truetype(str(font_path), size=size)
        probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = probe.textbbox((0, 0), char, font=font)
        glyph_w = max(1, bbox[2] - bbox[0])
        glyph_h = max(1, bbox[3] - bbox[1])
        pad = max(8, size // 3)
        glyph = Image.new("RGBA", (glyph_w + pad * 2, glyph_h + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(glyph)
        draw.text((pad - bbox[0], pad - bbox[1]), char, font=font, fill=color)
        angle = rotations[index] if index < len(rotations) else 0
        angle = position.get("rotation", angle)
        if angle:
            glyph = glyph.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        y_offset = px(offsets[index], height) if index < len(offsets) else 0
        canvas.alpha_composite(glyph, (x - pad, y + y_offset - pad))
        advance = round(font.getlength(char))
        x += advance + tracking


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--font", required=True)
    parser.add_argument("--spec", required=True, help="UTF-8 JSON file with a blocks array")
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=("standard", "ingredient-display"), default="standard")
    args = parser.parse_args()

    input_path = Path(args.input)
    font_path = Path(args.font)
    spec_path = Path(args.spec)
    output_path = Path(args.output)
    if not input_path.is_file() or not font_path.is_file() or not spec_path.is_file():
        raise FileNotFoundError("Input image, font, and spec must all exist")

    canvas = Image.open(input_path).convert("RGBA")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    blocks = spec.get("blocks", [])
    ingredient_mode = args.mode == "ingredient-display"
    if ingredient_mode:
        if len(blocks) != 4:
            raise ValueError("Ingredient display requires 4 text blocks: product name and 3 ingredient labels")
    elif not 1 <= len(blocks) <= 3:
        raise ValueError("Typography spec must contain 1 to 3 text blocks")
    max_chars = 40 if ingredient_mode else 10
    for block in blocks:
        if not block.get("text") or len(block["text"].replace("\n", "")) > max_chars:
            raise ValueError(f"Each text block must contain 1 to {max_chars} characters")
        render_block(canvas, font_path, block)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, quality=96)
    print(output_path.resolve())


if __name__ == "__main__":
    main()
