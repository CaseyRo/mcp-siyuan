FROM python:3.14-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY mcp_siyuan/ ./mcp_siyuan/
COPY healthcheck.py ./

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi8 libcairo2 fonts-noto \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir . \
    && addgroup --system mcp && adduser --system --ingroup mcp mcp

USER mcp

ENV TRANSPORT=http
ENV SIYUAN_URL=http://siyuan:6806
ENV HOST=0.0.0.0

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 /app/healthcheck.py

CMD ["mcp-siyuan"]
