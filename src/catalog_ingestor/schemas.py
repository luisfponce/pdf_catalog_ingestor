from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ProductCategory(StrEnum):
    ESSENTIAL_OIL = "essential_oil"
    ESSENTIAL_OIL_BLEND = "essential_oil_blend"
    PLUS_FLAVORING = "plus_flavoring"
    OTHER = "other"


class UsageMode(StrEnum):
    AROMATIC = "aromatic"
    TOPICAL = "topical"
    DILUTE = "dilute"
    FLAVORING = "flavoring"
    PHOTOSENSITIVE = "photosensitive"


class ProductVariant(BaseModel):
    sku: str
    size_value: float | None = None
    size_unit: str | None = None
    raw_size: str | None = None


class ProductImage(BaseModel):
    path: str
    format: str = "webp"
    source_page: int
    source_xref: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    sha256: str | None = None


class SourceRef(BaseModel):
    document_name: str
    page: int
    card_bbox: tuple[float, float, float, float] | None = None


class CanonicalProduct(BaseModel):
    # Canonical/source-derived fields
    name: str
    scientific_name: str | None = None
    category: ProductCategory = ProductCategory.OTHER
    description: str | None = None
    ingredients: list[str] = Field(default_factory=list)
    usage_text: str | None = None
    usage_modes: list[UsageMode] = Field(default_factory=list)
    variants: list[ProductVariant] = Field(default_factory=list)
    seasonal: bool = False

    # Media + provenance
    image: ProductImage | None = None
    source: SourceRef
    raw_text: str

    # Extraction metadata, never presented as source claims
    extraction_confidence: float = Field(default=1.0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    derived_tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_identity(self):
        if not self.name.strip():
            raise ValueError("product name is required")
        return self


class CatalogDocument(BaseModel):
    source_pdf: str
    products: list[CanonicalProduct]
    extraction_version: str = "0.1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
