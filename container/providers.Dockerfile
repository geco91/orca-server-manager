# syntax=docker/dockerfile:1
ARG RUNTIME_IMAGE=orca-server-manager/runtime:1.4.261
FROM python:3.12-slim-bookworm AS tools
ARG OPENCODE_VERSION=2.3.0
ARG OPENCODE_SHA256=fc0f81522aceeabac47693d88389efa2bc517ce74c2c38fd6967819fcc6e4d3b
COPY scripts/fetch-tools.py /fetch-tools.py
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    python /fetch-tools.py --opencode-version "$OPENCODE_VERSION" --opencode-sha256 "$OPENCODE_SHA256"
FROM $RUNTIME_IMAGE
COPY --from=tools /tools/ /usr/local/bin/
