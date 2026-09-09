from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from .schemas import CanonicalProduct


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "catalog_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class ProductRow(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("catalog_documents.id"), index=True)
    source_page: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    scientific_name: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    ingredients: Mapped[list] = mapped_column(JSONB, default=list)
    usage_text: Mapped[str | None] = mapped_column(Text)
    usage_modes: Mapped[list] = mapped_column(JSONB, default=list)
    seasonal: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_text: Mapped[str] = mapped_column(Text)
    extraction_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    derived_tags: Mapped[list] = mapped_column(JSONB, default=list)
    image_path: Mapped[str | None] = mapped_column(String(500))
    image_meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    variants: Mapped[list[VariantRow]] = relationship(cascade="all, delete-orphan")


class VariantRow(Base):
    __tablename__ = "product_variants"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    sku: Mapped[str] = mapped_column(String(64), index=True)
    size_value: Mapped[float | None] = mapped_column(Float)
    size_unit: Mapped[str | None] = mapped_column(String(32))
    raw_size: Mapped[str | None] = mapped_column(String(64))


def make_session_factory(database_url: str):
    engine = create_engine(database_url, future=True)
    return engine, sessionmaker(engine, expire_on_commit=False)


def init_db(database_url: str):
    engine, _ = make_session_factory(database_url)
    Base.metadata.create_all(engine)


def persist_catalog(database_url: str, filename: str, products: list[CanonicalProduct]):
    engine, Session = make_session_factory(database_url)
    Base.metadata.create_all(engine)
    with Session.begin() as session:
        doc = session.query(DocumentRow).filter_by(filename=filename).one_or_none()
        if doc is None:
            doc = DocumentRow(filename=filename, metadata_json={})
            session.add(doc)
            session.flush()
        else:
            # Idempotent first approach: replace products for the same source PDF.
            product_ids = select(ProductRow.id).where(ProductRow.document_id == doc.id)
            session.query(VariantRow).filter(VariantRow.product_id.in_(product_ids)).delete(
                synchronize_session=False,
            )
            session.query(ProductRow).filter_by(document_id=doc.id).delete(
                synchronize_session=False
            )
            session.flush()

        for p in products:
            row = ProductRow(
                document_id=doc.id,
                source_page=p.source.page,
                name=p.name,
                scientific_name=p.scientific_name,
                category=p.category.value,
                description=p.description,
                ingredients=p.ingredients,
                usage_text=p.usage_text,
                usage_modes=[m.value for m in p.usage_modes],
                seasonal=p.seasonal,
                raw_text=p.raw_text,
                extraction_confidence=p.extraction_confidence,
                warnings=p.warnings,
                derived_tags=p.derived_tags,
                image_path=p.image.path if p.image else None,
                image_meta=p.image.model_dump() if p.image else {},
            )
            row.variants = [VariantRow(**v.model_dump()) for v in p.variants]
            session.add(row)
