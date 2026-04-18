FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY mcp_siyuan/ ./mcp_siyuan/

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

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python3 -c "import urllib.request,json,sys; r=urllib.request.urlopen('http://localhost:8000/health',timeout=3); d=json.loads(r.read()); sys.exit(0 if d.get('status')=='healthy' else 1)"

CMD ["mcp-siyuan"]
