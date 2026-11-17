# syntax=docker/dockerfile:1
FROM caddy:2.10.2 AS caddy
RUN setcap -r /usr/bin/caddy
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
RUN apt-get update && apt-get install -y --no-install-recommends openssl tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home manager
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY manager ./manager
RUN chmod -R a+rX /app/manager
COPY container/manager-service.py /app/manager-service.py
COPY container/manager.Caddyfile /etc/caddy/Caddyfile
ENV OSM_STATE_DIR=/data/manager OSM_CONTROL_DIR=/control \
    PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1
EXPOSE 80 443
HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
    CMD ["python", "-c", "from urllib.request import build_opener,ProxyHandler; build_opener(ProxyHandler({})).open('http://127.0.0.1:8080/healthz',timeout=3)"]
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "/app/manager-service.py"]
