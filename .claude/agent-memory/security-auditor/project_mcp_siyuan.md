---
name: mcp-siyuan security posture
description: Architecture, key findings, and security posture of the mcp-siyuan FastMCP server project
type: project
---

Python FastMCP 3.x MCP server for SiYuan Notes. Runs as Docker sidecar alongside SiYuan kernel. Exposes MCP tools over streamable HTTP and stdio. Uses httpx async client, pydantic-settings config.

**Key findings from 2026-03-20 audit:**

- `siyuan_sql_query` in `mcp_siyuan/tools/read.py` passes the `stmt` parameter directly to SiYuan's `/api/query/sql` endpoint with no validation — full SQL injection risk for LLM prompt injection attacks
- `SIYUAN_TOKEN` uses plain `str` type in pydantic-settings config (not `SecretStr`) — token may be exposed in logs/repr output
- Docker container runs as root (no USER directive in Dockerfile)
- MCP HTTP server binds to `0.0.0.0:8000` by default with no authentication layer
- SiYuan kernel port 6806 is published to host in docker-compose, unnecessarily widening attack surface
- `siyuan_get_document` has a broken f-string at line 38 (bug, not security issue, but shows lack of testing coverage)
- `data_type` parameter in write tools accepts arbitrary strings, not validated to the "markdown"/"dom" enum
- `max_length` and `limit` parameters have no upper bound validation — potential for resource exhaustion
- `SIYUAN_URL` accepts arbitrary URLs with no validation — SSRF vector if attacker can control config
- No network isolation between siyuan and mcp-siyuan services (both on default bridge network, both publicly reachable)

**Why:** Initial audit before any security hardening has been performed.
**How to apply:** Reference when the user asks about security fixes, prioritize SQL injection and root container as the most impactful items.
