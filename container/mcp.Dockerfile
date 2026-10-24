# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS source
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export CURL_CA_BUNDLE=/run/secrets/proxy_ca; fi; \
    curl --fail --location --retry 3 https://codeload.github.com/BuildContext/orca-mcp/tar.gz/8e355dd72d168aa81c85d8003cdfeb53821f4de1 -o /tmp/bridge.tar.gz \
    && echo '669199e9bdb9890b6f7f3d5a5e7c5a4307f9efa4be76b37b8725de42acc82c45  /tmp/bridge.tar.gz' | sha256sum -c - \
    && mkdir /bridge && tar xzf /tmp/bridge.tar.gz --strip-components=1 -C /bridge
FROM orca-server-manager/runtime:0.1.0
COPY --from=source /bridge /opt/orca-mcp
COPY --chmod=755 container/bridge /usr/local/bin/bridge
COPY --chmod=644 scripts/mcp-smoke.mjs /usr/local/lib/mcp-health.mjs
WORKDIR /workspaces
ENV ORCA_CLI_COMMAND=orca ORCA_BRIDGE_TOOLSETS=status ORCA_BRIDGE_CLI_HARDENING=1
HEALTHCHECK --interval=30s --timeout=20s --start-period=20s --retries=3 \
    CMD ["node", "/usr/local/lib/mcp-health.mjs"]
CMD ["bridge"]
