FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 catalog \
    && useradd --uid 10001 --gid catalog --no-create-home --shell /usr/sbin/nologin catalog

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir . \
    && mkdir -p /data/input /data/output \
    && chown -R catalog:catalog /data

USER catalog
WORKDIR /data

ENTRYPOINT ["yl-catalog"]
CMD ["--help"]
