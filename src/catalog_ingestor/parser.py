from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .extractor import PageLayout, TextBlock
from .image_utils import save_xref_as_webp, slugify
from .schemas import (
    CanonicalProduct,
    ProductCategory,
    ProductImage,
    ProductVariant,
    SourceRef,
    UsageMode,
)

SKU_MARKER_RE = re.compile(r"SKU\s+(?:TAMAÑO|CANTIDAD)\b", re.IGNORECASE)
SKU_RE = re.compile(r"\b\d{5,6}\b")
SIZE_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(tabletas?|pk|caps?|cápsulas?|g|ml|unidades?)\b",
    re.IGNORECASE,
)
SCI_RE = re.compile(r"^[A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ]+(?:\s+[a-z][A-Za-záéíóúñ]+){1,2}$")
IGNORED = {
    "MODO DE USO |",
    "FOTOSENSIBILIDAD TÓPICO DILUIR AROMÁTICO SABORIZANTE",
    "SALUD ES BELLEZA",
    "Aceites Esenciales",
    "Mezclas de Aceites Esenciales",
    "ACEITES ESENCIALES Y PRODUCTOS INFUNDIDOS CON ACEITES ESENCIALES",
    "Línea Plus",
    "PRODUCTOS DE TEMPORADA",
    "ORIGEN",
    "CIENCIA",
    "ESTÁNDARES",
    "NUESTRO COMPROMISO",
    "SUSTENTABILIDAD, CALIDAD Y PROPÓSITO:",
    "Vida Activa y en Forma",
    "TABLA CONTENIDO",
}
IGNORED_PREFIXES = (
    "SKU ",
    "INGREDIENTES",
    "MODO DE USO",
    "FOTOSENSIBILIDAD",
    "ACEITES ESENCIALES Y PRODUCTOS INFUNDIDOS",
    "Estos productos no están destinados",
    "Estos productos no son un medicamento",
    "SKU CANTIDAD",
    "SOBRES INDIVIDUALES",
)
MIN_IMAGE_AREA_RATIO = 0.015


@dataclass(slots=True)
class Card:
    text_bbox: tuple[float, float, float, float]
    image_bbox: tuple[float, float, float, float]
    blocks: list[TextBlock]

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)


def split_into_quadrants(layout: PageLayout) -> list[Card]:
    # Text cells never overlap. Images use gutter-aware bounds because bottles sit left of the text.
    w, h = layout.width, layout.height
    row_boundary = h * 0.55
    image_boxes = [
        (40, 90, w / 2 + 10, row_boundary + 10),
        (w / 2 - 10, 90, w - 10, row_boundary + 10),
        (40, row_boundary - 10, w / 2 + 10, h - 45),
        (w / 2 - 10, row_boundary - 10, w - 10, h - 45),
    ]
    return [
        Card(cell.bbox, image_bbox, cell.blocks)
        for cell, image_bbox in zip(layout.text_cells, image_boxes, strict=True)
    ]


def layout_adapter(layout: PageLayout) -> str | None:
    text = "\n".join(cell.text for cell in split_into_quadrants(layout))
    if re.search(r"SKU\s+TAMAÑO\b", text, re.IGNORECASE):
        return "four_cell_size"
    if re.search(r"SKU\s+CANTIDAD\b", text, re.IGNORECASE):
        return "four_cell_quantity"
    return None


def detect_category(page_number: int) -> ProductCategory:
    if 26 <= page_number <= 29:
        return ProductCategory.PLUS_FLAVORING
    if 31 <= page_number <= 40:
        return ProductCategory.ESSENTIAL_OIL_BLEND
    if 15 <= page_number <= 25:
        return ProductCategory.ESSENTIAL_OIL
    return ProductCategory.OTHER


def _candidate_name(blocks: list[TextBlock]) -> str | None:
    for index, b in enumerate(blocks):
        t = b.text.strip()
        if t in IGNORED or t.startswith(IGNORED_PREFIXES):
            continue
        # Product headings are uppercase and short; punctuation and trademark markers are valid.
        if 2 <= len(t) <= 80 and any(c.isalpha() for c in t):
            alpha = "".join(c for c in t if c.isalpha())
            if alpha and alpha.upper() == alpha:
                heading_lines = [t]
                previous_y1 = b.bbox[3]
                for continuation in blocks[index + 1 :]:
                    candidate = continuation.text.strip()
                    candidate_alpha = "".join(c for c in candidate if c.isalpha())
                    if (
                        continuation.bbox[1] - previous_y1 > 8
                        or candidate in IGNORED
                        or candidate.startswith(IGNORED_PREFIXES)
                        or not candidate_alpha
                        or candidate_alpha.upper() != candidate_alpha
                    ):
                        break
                    heading_lines.append(candidate)
                    previous_y1 = continuation.bbox[3]
                return " ".join(heading_lines).replace("*", "").replace("™", "").strip()
    return None


def _parse_variants(text: str) -> list[ProductVariant]:
    normalized = re.sub(r"\s+", " ", text.replace("|", " ")).strip()
    marker = SKU_MARKER_RE.search(normalized)
    if not marker:
        return []
    tail = normalized[marker.end() :]
    sku_matches = list(SKU_RE.finditer(tail))
    variants: list[ProductVariant] = []
    for index, sku_match in enumerate(sku_matches):
        end = sku_matches[index + 1].start() if index + 1 < len(sku_matches) else len(tail)
        size_text = tail[sku_match.end() : end].strip(" |-.,")
        size = SIZE_RE.match(size_text)
        if size:
            value, unit = size.groups()
            raw_size = size.group(0)
            package_detail = re.match(
                r"\s*-\s*\d+(?:[.,]\d+)?\s*(?:ml|g)\s*c/u\b",
                size_text[size.end() :],
                re.IGNORECASE,
            )
            if package_detail:
                raw_size += package_detail.group(0)
            variants.append(
                ProductVariant(
                    sku=sku_match.group(),
                    size_value=float(value.replace(",", ".")),
                    size_unit=unit.lower(),
                    raw_size=raw_size,
                )
            )
        else:
            variants.append(ProductVariant(sku=sku_match.group()))
    return variants


def _variant_warnings(variants: list[ProductVariant]) -> list[str]:
    if not variants:
        return ["variant_parse_failed"]
    if any(v.size_value is None or v.size_unit is None for v in variants):
        return ["variant_size_parse_failed"]
    return []


def _parse_scientific_name(blocks: list[TextBlock], name: str) -> str | None:
    seen_name = False
    for b in blocks:
        t = b.text.strip()
        if t == name or t.replace("*", "").replace("™", "").strip() == name:
            seen_name = True
            continue
        if seen_name and SCI_RE.match(t) and "SKU" not in t:
            return t
    return None


def _scientific_names(blocks: list[TextBlock]) -> list[str]:
    return [block.text.strip() for block in blocks if SCI_RE.match(block.text.strip())]


def _parse_ingredients(text: str) -> list[str]:
    m = re.search(
        r"INGREDIENTES\s*\|\s*(.+?)(?=\nMODO DE USO|\nSKU|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    raw = re.sub(r"\s+", " ", m.group(1)).strip(" .")
    parts = re.split(r",|\sy\s", raw)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def _usage(text: str) -> tuple[str | None, list[UsageMode]]:
    m = re.search(
        r"MODO DE USO\s*\|\s*(.+?)(?=\nINGREDIENTES|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    usage = re.sub(r"\s+", " ", m.group(1)).strip() if m else None
    modes: list[UsageMode] = []
    low = (usage or "").lower()
    if "difusor" in low or "inhal" in low:
        modes.append(UsageMode.AROMATIC)
    if "piel" in low or "tópic" in low or "masaje" in low:
        modes.append(UsageMode.TOPICAL)
    if "diluir" in low:
        modes.append(UsageMode.DILUTE)
    if "receta" in low or "sabor" in low or "bebida" in low:
        modes.append(UsageMode.FLAVORING)
    return usage, modes


def _description(blocks: list[TextBlock], name: str) -> str | None:
    excluded_prefixes = ("SKU ", "INGREDIENTES", "FOTOSENSIBILIDAD")
    parts = []
    for b in blocks:
        t = b.text.strip()
        if t.startswith("MODO DE USO"):
            break
        cleaned = t.replace("*", "").replace("™", "").strip()
        if cleaned == name or t.startswith(excluded_prefixes):
            continue
        if SCI_RE.match(t):
            continue
        # Skip compact SKU/size blocks and obvious headers.
        if re.search(r"\b\d{5,6}\b", t) and ("SKU" in t or "ml" in t.lower()):
            continue
        if t not in IGNORED and (parts or len(t) > 35):
            parts.append(t)
    return " ".join(parts) if parts else None


def _nearest_image(layout: PageLayout, card: Card, used_images: set[tuple]):
    card_bbox = card.image_bbox
    bx0, by0, bx1, by1 = card_bbox
    card_area = (bx1 - bx0) * (by1 - by0)
    min_area = card_area * MIN_IMAGE_AREA_RATIO
    text_x0, text_y0, _, text_y1 = card.text_bbox
    anchor = (text_x0, (text_y0 + text_y1) / 2)
    candidates = []
    for image in layout.images:
        key = (layout.page_number, image.xref, image.bbox)
        if key in used_images:
            continue
        x0, y0, x1, y1 = image.bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        area = (x1 - x0) * (y1 - y0)
        if area < min_area:
            continue
        if bx0 <= cx <= bx1 and by0 <= cy <= by1:
            distance = (cx - anchor[0]) ** 2 + (cy - anchor[1]) ** 2
            candidates.append((distance, -area, image))
    if not candidates:
        return None
    image = min(candidates, key=lambda item: (item[0], item[1]))[2]
    used_images.add((layout.page_number, image.xref, image.bbox))
    return image


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    return list(dict.fromkeys(warnings))


def parse_page(
    doc: pymupdf.Document, layout: PageLayout, source_name: str, image_dir: Path
) -> list[CanonicalProduct]:
    if not layout_adapter(layout):
        return []
    out: list[CanonicalProduct] = []
    used_images: set[tuple] = set()
    for card in split_into_quadrants(layout):
        if not card.blocks:
            continue
        name = _candidate_name(card.blocks)
        if not name:
            continue
        text = card.text
        marker_count = len(SKU_MARKER_RE.findall(text))
        if marker_count == 0:
            continue
        usage_text, usage_modes = _usage(text)
        image_meta = None
        img = _nearest_image(layout, card, used_images)
        if img:
            path = image_dir / f"p{layout.page_number:02d}-{slugify(name)}.webp"
            try:
                digest = save_xref_as_webp(doc, img.xref, path)
                image_meta = ProductImage(
                    path=str(path),
                    source_page=layout.page_number,
                    source_xref=img.xref,
                    bbox=img.bbox,
                    sha256=digest,
                )
            except (KeyError, OSError, RuntimeError, ValueError):
                image_meta = None
        variants = _parse_variants(text)
        warnings = _variant_warnings(variants)
        scientific_names = _scientific_names(card.blocks)
        if marker_count > 1:
            warnings.append("repeated_sku_marker")
        if len(scientific_names) > 1:
            warnings.append("multiple_scientific_names")
        if not image_meta:
            warnings.append("image_match_failed")
        if warnings:
            warnings.append("low_confidence")
        product = CanonicalProduct(
            name=name,
            scientific_name=_parse_scientific_name(card.blocks, name),
            category=detect_category(layout.page_number),
            description=_description(card.blocks, name),
            ingredients=_parse_ingredients(text),
            usage_text=usage_text,
            usage_modes=usage_modes,
            variants=variants,
            seasonal="Producto de temporada" in text,
            image=image_meta,
            source=SourceRef(
                document_name=source_name, page=layout.page_number, card_bbox=card.text_bbox
            ),
            raw_text=text,
            extraction_confidence=0.90 if variants and image_meta else 0.72,
            warnings=warnings,
        )
        product.warnings = _dedupe_warnings(product.warnings)
        out.append(product)

    sku_products: dict[str, list[CanonicalProduct]] = {}
    for product in out:
        for variant in product.variants:
            sku_products.setdefault(variant.sku, []).append(product)
    for products in sku_products.values():
        if len(products) > 1:
            for product in products:
                product.warnings = _dedupe_warnings(
                    [*product.warnings, "duplicate_sku", "low_confidence"]
                )

    for product in out:
        description = (product.description or "").casefold()
        own_name = product.name.casefold()
        if (
            description
            and own_name not in description
            and any(other.name.casefold() in description for other in out if other is not product)
        ):
            product.warnings = _dedupe_warnings(
                [
                    *product.warnings,
                    "description_identity_mismatch",
                    "low_confidence",
                ]
            )
    return out
