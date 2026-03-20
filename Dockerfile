FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY mcp_siyuan/ ./mcp_siyuan/

RUN pip install --no-cache-dir . && \
    addgroup --system mcp && adduser --system --ingroup mcp mcp

USER mcp

ENV TRANSPORT=http
ENV SIYUAN_URL=http://siyuan:6806
ENV HOST=0.0.0.0

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "from urllib.request import urlopen;from urllib.error import HTTPError,URLError;exec('try:\n urlopen(\"http://localhost:8000/mcp\")\nexcept HTTPError:\n pass\nexcept URLError:\n raise')"

CMD ["mcp-siyuan"]
