# syntax=docker/dockerfile:1
ARG RUNTIME_IMAGE=orca-server-manager/runtime:1.4.261
FROM python:3.12-slim-bookworm AS tools
ARG OPENCODE_VERSION=1.19.5
ARG OPENCODE_SHA256=588310a336fa3b9df36b3f0225b26f679d453efaad0cf3d66c3651ef3ec1647a
COPY scripts/fetch-tools.py /fetch-tools.py
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    python /fetch-tools.py --opencode-version "$OPENCODE_VERSION" --opencode-sha256 "$OPENCODE_SHA256"
FROM $RUNTIME_IMAGE
COPY --from=tools /tools/codex /tools/opencode /usr/local/bin/
