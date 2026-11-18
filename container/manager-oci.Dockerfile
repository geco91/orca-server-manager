# syntax=docker/dockerfile:1
FROM caddy:2.10.2 AS caddy
RUN setcap -r /usr/bin/caddy
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.12-slim-bookworm AS app
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --no-dev --no-install-project
COPY manager ./manager
RUN chmod -R a+rX /app/manager
COPY --chmod=0644 container/manager-service.py container/browser-service.py container/browser-native.cjs /app/
COPY --chmod=0644 container/manager.Caddyfile /app/manager.Caddyfile

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
RUN --mount=type=secret,id=proxy_ca,mode=0444 \
    sed -i 's|http://deb.debian.org/|https://deb.debian.org/|g' /etc/apt/sources.list.d/debian.sources \
    && if [ -f /run/secrets/proxy_ca ]; then echo 'Acquire::https::CaInfo "/run/secrets/proxy_ca";' > /etc/apt/apt.conf.d/99build-ca; fi \
    && apt-get update && apt-get install -y --no-install-recommends openssl tini xvfb xauth dbus-daemon \
    libgtk-3-0 libnotify4 libnss3 libxss1 libxtst6 libatspi2.0-0 libuuid1 libsecret-1-0 \
    libasound2 libgbm1 libdrm2 fonts-liberation git xdg-utils qrencode \
    && rm -rf /var/lib/apt/lists/* /etc/apt/apt.conf.d/99build-ca \
    && useradd --uid 1000 --create-home manager \
    && useradd --uid 1001 --user-group --no-create-home --home-dir /data/browser --shell /usr/sbin/nologin orca-browser \
    && mkdir -p /etc/caddy && ln -s /app/manager.Caddyfile /etc/caddy/Caddyfile
ARG ORCA_VERSION=1.4.261
ARG ORCA_ARCH=x64
ARG ORCA_WEB_SHA256=86755b4c6e7e25d2ef4aadd5d2508bf52520d15f8ef45fa99e74cec7431e5c1c
RUN --mount=type=secret,id=proxy_ca --mount=type=bind,source=scripts/fetch-web.py,target=/build/fetch-web.py \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    python /build/fetch-web.py "$ORCA_VERSION" "$ORCA_ARCH" "$ORCA_WEB_SHA256" /tmp/orca.deb --package \
    && dpkg-deb --fsys-tarfile /tmp/orca.deb | tar -x -C / ./opt/Orca \
    && rm /tmp/orca.deb && chmod 4755 /opt/Orca/chrome-sandbox
COPY --from=app /app /app
ENV OSM_STATE_DIR=/data/manager OSM_CONTROL_DIR=/control \
    PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1
EXPOSE 80 443
HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
    CMD ["python", "-c", "from urllib.request import build_opener,ProxyHandler; build_opener(ProxyHandler({})).open('http://127.0.0.1:8080/healthz',timeout=3)"]
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "/app/manager-service.py"]
