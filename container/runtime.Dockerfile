# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS assemble
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=proxy_ca \
    mkdir -p /build && \
    if [ -f /run/secrets/proxy_ca ]; then export CURL_CA_BUNDLE=/run/secrets/proxy_ca; fi; \
    curl --fail --location --retry 3 https://github.com/stablyai/orca/releases/download/v1.4.239/orca-ide_1.4.239_amd64.deb -o /build/orca.deb \
    && curl --fail --location --retry 3 https://nodejs.org/dist/v24.22.1/node-v24.22.1-linux-x64.tar.xz -o /build/node.tar.xz
COPY scripts/materialize-runtime.py /build/materialize-runtime.py
RUN python /build/materialize-runtime.py /build/orca.deb /build/node.tar.xz /opt/orca

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git gh openssh-client procps libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home --shell /bin/bash orca \
    && mkdir -p /workspaces && chown orca:orca /workspaces
COPY --from=assemble /opt/orca /opt/orca
RUN ln -s "/opt/orca/runtimes/node-$(cat /opt/orca/server/.runtime-node)/bin" /opt/orca/node-bin
COPY --chmod=755 container/orca container/orcad /usr/local/bin/
COPY --chmod=644 container/runtime-health.cjs /usr/local/lib/runtime-health.cjs
COPY LICENSE /usr/share/doc/orca-server-manager/LICENSE
COPY docs/licenses/Orca-MIT.txt /usr/share/doc/orca/LICENSE
USER 1000:1000
ENV HOME=/home/orca ORCA_USER_DATA=/home/orca/.config/Orca \
    ORCA_USER_DATA_PATH=/home/orca/.config/Orca ORCA_VERSION=1.4.239 \
    ORCA_TELEMETRY_DISABLED=1 \
    NODE_USE_ENV_PROXY=1 \
    PATH=/opt/orca/node-bin:/usr/local/bin:/usr/bin:/bin
WORKDIR /workspaces
EXPOSE 6768
HEALTHCHECK --interval=20s --timeout=10s --start-period=60s --retries=3 \
    CMD ["node", "/usr/local/lib/runtime-health.cjs"]
CMD ["orcad", "--bind", "0.0.0.0", "--port", "6768", "--no-pairing", "--web-client-root", "/opt/orca/web"]
