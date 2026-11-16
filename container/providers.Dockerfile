# syntax=docker/dockerfile:1
ARG RUNTIME_IMAGE=orca-server-manager/runtime:1.4.261
FROM python:3.12-slim-bookworm AS tools
COPY scripts/fetch-tools.py /fetch-tools.py
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    python /fetch-tools.py
FROM $RUNTIME_IMAGE
COPY --from=tools /tools/codex /tools/opencode /usr/local/bin/
