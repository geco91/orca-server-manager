# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS assemble
ARG ORCA_VERSION=1.4.261
ARG ORCA_ARCH=x64
ARG ORCA_SHA256=fdb65eb961d3d4c1959601a51bc9bc5663b0403369ad50a422af16947ac3f3ba
ARG ORCA_WEB_SHA256=86755b4c6e7e25d2ef4aadd5d2508bf52520d15f8ef45fa99e74cec7431e5c1c
COPY scripts/fetch-server.py /build/fetch-server.py
COPY scripts/fetch-web.py /build/fetch-web.py
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    python /build/fetch-server.py "$ORCA_VERSION" "$ORCA_ARCH" "$ORCA_SHA256" /opt/orca
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    if [ -n "$ORCA_WEB_SHA256" ]; then \
      python /build/fetch-web.py "$ORCA_VERSION" "$ORCA_ARCH" "$ORCA_WEB_SHA256" /tmp/orca.deb --package \
      && dpkg-deb -x /tmp/orca.deb /desktop \
      && python /build/fetch-web.py "$ORCA_VERSION" "$ORCA_ARCH" "$ORCA_WEB_SHA256" /opt/orca/out/web --from-package /tmp/orca.deb \
      && rm /tmp/orca.deb; \
    else mkdir -p /desktop/opt/Orca; fi
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    python -c 'import urllib.request; urllib.request.urlretrieve("https://codeload.github.com/BuildContext/orca-mcp/tar.gz/8e355dd72d168aa81c85d8003cdfeb53821f4de1","/tmp/bridge.tar.gz")'
RUN echo '669199e9bdb9890b6f7f3d5a5e7c5a4307f9efa4be76b37b8725de42acc82c45  /tmp/bridge.tar.gz' | sha256sum -c - \
    && mkdir /opt/orca-mcp && tar xzf /tmp/bridge.tar.gz --strip-components=1 -C /opt/orca-mcp

FROM debian:bookworm-slim
RUN --mount=type=secret,id=proxy_ca,mode=0444 \
    sed -i 's|http://deb.debian.org/|https://deb.debian.org/|g' /etc/apt/sources.list.d/debian.sources \
    && if [ -f /run/secrets/proxy_ca ]; then echo 'Acquire::https::CaInfo "/run/secrets/proxy_ca";' > /etc/apt/apt.conf.d/99build-ca; fi \
    && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git gh openssh-client procps libstdc++6 tini util-linux \
    python3 xvfb xauth dbus-daemon libgtk-3-0 libnotify4 libnss3 libxss1 libxtst6 libatspi2.0-0 \
    libuuid1 libsecret-1-0 libasound2 libgbm1 libdrm2 fonts-liberation xdg-utils \
    && rm -rf /var/lib/apt/lists/* /etc/apt/apt.conf.d/99build-ca \
    && useradd --uid 1000 --create-home --shell /bin/bash orca \
    && mkdir -p /workspaces /opt/osm && chmod 755 /opt/osm && chown orca:orca /workspaces
COPY --from=assemble /desktop/opt/Orca /opt/Orca
RUN if [ -f /opt/Orca/chrome-sandbox ]; then chmod 4755 /opt/Orca/chrome-sandbox; fi
COPY --from=assemble /opt/orca /opt/orca
COPY --from=assemble /opt/orca-mcp /opt/orca-mcp
RUN ln -s /opt/orca/bin/orca-ide /usr/local/bin/orca \
    && ln -s "/opt/orca/runtimes/node-$(cat /opt/orca/orcad/.runtime-node)/bin" /opt/orca/node-bin
COPY --chmod=644 container/runtime-health.cjs container/runtime-status.cjs container/runtime-launch.cjs container/opencode-default.cjs container/forge.cjs /opt/osm/
COPY --chmod=644 container/browser-service.py container/browser-native.cjs /opt/osm/
COPY --chmod=644 scripts/mcp-smoke.mjs /opt/osm/mcp-health.mjs
USER 1000:1000
ENV HOME=/home/orca ORCA_USER_DATA=/home/orca/.config/Orca \
    ORCA_USER_DATA_PATH=/home/orca/.config/Orca ORCA_TELEMETRY_DISABLED=1 \
    NODE_USE_ENV_PROXY=1 PATH=/opt/orca/node-bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /workspaces
EXPOSE 6768 6770
HEALTHCHECK --interval=20s --timeout=15s --start-period=90s --retries=3 \
    CMD ["node", "/opt/osm/runtime-health.cjs"]
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "/opt/osm/runtime-launch.cjs"]
