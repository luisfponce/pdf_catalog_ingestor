from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import pymupdf
from PIL import Image


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "product"


def save_xref_as_webp(doc: pymupdf.Document, xref: int, output_path: Path) -> str:
    payload = doc.extract_image(xref)
    image = Image.open(io.BytesIO(payload["image"])).convert("RGBA")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "WEBP", quality=88, method=6)
    return hashlib.sha256(output_path.read_bytes()).hexdigest()
