from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(slots=True)
class TextBlock:
    bbox: tuple[float, float, float, float]
    text: str


@dataclass(slots=True)
class PositionedWord:
    bbox: tuple[float, float, float, float]
    text: str


@dataclass(slots=True)
class TextCell:
    bbox: tuple[float, float, float, float]
    blocks: list[TextBlock]

    @property
    def text(self) -> str:
        return "\n".join(block.text for block in self.blocks)


@dataclass(slots=True)
class PageImage:
    xref: int
    bbox: tuple[float, float, float, float]


@dataclass(slots=True)
class PageLayout:
    page_number: int
    width: float
    height: float
    text_blocks: list[TextBlock]
    images: list[PageImage]
    text_cells: list[TextCell]


def product_text_bboxes(width: float, height: float) -> list[tuple[float, float, float, float]]:
    midpoint = width / 2
    row_boundary = height * 0.55
    return [
        (40, 90, midpoint, row_boundary),
        (midpoint, 90, width - 10, row_boundary),
        (40, row_boundary, midpoint, height - 45),
        (midpoint, row_boundary, width - 10, height - 45),
    ]


def _inside_bbox(word: PositionedWord, bbox: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = word.bbox
    bx0, by0, bx1, by1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return bx0 <= cx < bx1 and by0 <= cy < by1


def _reconstruct_lines(
    words: list[PositionedWord], baseline_tolerance: float = 3.0
) -> list[TextBlock]:
    lines: list[list[PositionedWord]] = []
    for word in sorted(words, key=lambda item: (((item.bbox[1] + item.bbox[3]) / 2), item.bbox[0])):
        baseline = (word.bbox[1] + word.bbox[3]) / 2
        if not lines:
            lines.append([word])
            continue
        previous_baseline = sum((w.bbox[1] + w.bbox[3]) / 2 for w in lines[-1]) / len(lines[-1])
        if abs(baseline - previous_baseline) <= baseline_tolerance:
            lines[-1].append(word)
        else:
            lines.append([word])

    blocks: list[TextBlock] = []
    for line in lines:
        line.sort(key=lambda item: item.bbox[0])
        blocks.append(
            TextBlock(
                bbox=(
                    min(word.bbox[0] for word in line),
                    min(word.bbox[1] for word in line),
                    max(word.bbox[2] for word in line),
                    max(word.bbox[3] for word in line),
                ),
                text=" ".join(word.text for word in line),
            )
        )
    return blocks


def reconstruct_text_cells(
    words: list[PositionedWord],
    width: float,
    height: float,
) -> list[TextCell]:
    cells: list[TextCell] = []
    for bbox in product_text_bboxes(width, height):
        cell_words = [word for word in words if _inside_bbox(word, bbox)]
        cells.append(TextCell(bbox=bbox, blocks=_reconstruct_lines(cell_words)))
    return cells


def extract_layout(pdf_path: Path) -> tuple[pymupdf.Document, list[PageLayout]]:
    doc = pymupdf.open(pdf_path)
    layouts: list[PageLayout] = []
    for page_index, page in enumerate(doc):
        blocks = []
        for block in page.get_text("blocks", sort=True):
            x0, y0, x1, y1, text = block[:5]
            text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
            if text:
                blocks.append(TextBlock((x0, y0, x1, y1), text))

        words = [
            PositionedWord((word[0], word[1], word[2], word[3]), word[4])
            for word in page.get_text("words", sort=True)
            if word[4].strip()
        ]

        images: list[PageImage] = []
        seen: set[tuple[int, int, int, int, int]] = set()
        for item in page.get_images(full=True):
            xref = item[0]
            for rect in page.get_image_rects(xref):
                key = (xref, round(rect.x0), round(rect.y0), round(rect.x1), round(rect.y1))
                if key in seen:
                    continue
                seen.add(key)
                images.append(PageImage(xref, (rect.x0, rect.y0, rect.x1, rect.y1)))

        layouts.append(
            PageLayout(
                page_index + 1,
                page.rect.width,
                page.rect.height,
                blocks,
                images,
                reconstruct_text_cells(words, page.rect.width, page.rect.height),
            )
        )
    return doc, layouts
