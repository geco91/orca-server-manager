# syntax=docker/dockerfile:1
ARG RUNTIME_IMAGE=orca-server-manager/runtime:1.4.261
FROM python:3.12-slim-bookworm AS tools
ARG OPENCODE_VERSION=2.3.0
ARG OPENCODE_SHA256=fc0f81522aceeabac47693d88389efa2bc517ce74c2c38fd6967819fcc6e4d3b
COPY scripts/fetch-tools.py /fetch-tools.py
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    python /fetch-tools.py --opencode-version "$OPENCODE_VERSION" --opencode-sha256 "$OPENCODE_SHA256"
FROM caddy:2.10.2 AS caddy
RUN setcap -r /usr/bin/caddy
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.12-slim-bookworm AS dashboard
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY manager ./manager
RUN chmod -R a+rX /app/manager
COPY --chmod=0644 container/manager-service.py container/manager.Caddyfile /app/

FROM $RUNTIME_IMAGE
USER 0:0
RUN --mount=type=secret,id=proxy_ca,mode=0444 \
    if [ -f /run/secrets/proxy_ca ]; then echo 'Acquire::https::CaInfo "/run/secrets/proxy_ca";' > /etc/apt/apt.conf.d/99build-ca; fi \
    && apt-get update && apt-get install -y --no-install-recommends openssl qrencode \
    && rm -rf /var/lib/apt/lists/* /etc/apt/apt.conf.d/99build-ca \
    && useradd --uid 1001 --user-group --create-home manager
COPY --from=tools /tools/ /usr/local/bin/
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
COPY --from=dashboard /app /app
ENV OSM_STATE_DIR=/data/manager OSM_CONTROL_DIR=/control \
    OSM_ORCA_UPSTREAM=127.0.0.1:6768 PYTHONDONTWRITEBYTECODE=1
EXPOSE 80 443 6770
HEALTHCHECK --interval=20s --timeout=15s --start-period=90s --retries=3 \
    CMD setpriv --reuid 1000 --regid 1000 --clear-groups node /opt/osm/runtime-health.cjs \
        && python -c "import urllib.request; urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8080/healthz', timeout=3)"
CMD ["/usr/local/bin/python3", "/app/manager-service.py"]
