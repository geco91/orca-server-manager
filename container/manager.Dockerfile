# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY --chown=1000:1000 manager ./manager
RUN useradd --uid 1000 --create-home manager && mkdir /data && chown manager:manager /data
USER 1000:1000
ENV OSM_STATE_DIR=/data PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"]
CMD ["gunicorn", "--bind=0.0.0.0:8080", "--workers=1", "--threads=4", "--umask=0077", "--no-control-socket", "manager.app:create_app()"]
