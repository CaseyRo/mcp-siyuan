FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY mcp_siyuan/ ./mcp_siyuan/

RUN pip install --no-cache-dir . && \
    addgroup --system mcp && adduser --system --ingroup mcp mcp

USER mcp

ENV TRANSPORT=http
ENV SIYUAN_URL=http://siyuan:6806
ENV HOST=0.0.0.0

EXPOSE 8000

CMD ["mcp-siyuan"]
