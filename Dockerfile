FROM python:3.12-slim AS builder

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install EXACTLY what uv.lock pins — never re-resolve at build time.
# (Incident 2026-07-07 on mcp-stolperstein: an unpinned `pip install .` here
# silently picked up a newer fastmcp whose Host-header guard 421'd all of
# production. `uv sync --frozen` refuses to deviate from the lockfile.)
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY mcp_siyuan/ mcp_siyuan/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi8 libcairo2 fonts-noto \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system mcp && adduser --system --ingroup mcp mcp

COPY --from=builder /app/.venv /app/.venv
COPY mcp_siyuan/ ./mcp_siyuan/
COPY healthcheck.py ./

ENV PATH="/app/.venv/bin:$PATH"

USER mcp

ENV TRANSPORT=http
ENV SIYUAN_URL=http://siyuan:6806
ENV HOST=0.0.0.0

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 /app/healthcheck.py

CMD ["mcp-siyuan"]
