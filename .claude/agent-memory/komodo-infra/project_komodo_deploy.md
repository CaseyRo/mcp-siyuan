---
name: project_komodo_deploy
description: Komodo/km CLI deployment pattern and known issues for mcp-siyuan on Hetzner (ubuntu-smurf-mirror)
type: project
---

## git-mcp-siyuan Stack on Komodo

Stack `git-mcp-siyuan` registered in Komodo Core on 2026-03-23 via direct API (`CreateStack` write endpoint).
- Stack ID: `69c13bb0c2ece4f20873e622`
- Server: `ubuntu-smurf-mirror` (ID: `6977391729c5422ae385955f`)
- Repo: `CaseyRo/mcp-siyuan`, branch `main`
- `run_build: true` — compose.yaml uses `build: .`
- Komodo variables: `SIYUAN_TOKEN` (secret), `MCP_SIYUAN_API_KEY` (secret)
- Deploy: `echo "" | km execute deploy-stack git-mcp-siyuan`

**Why:** Stack was previously deployed manually to `/etc/komodo/stacks/git-mcp-siyuan/`. Now managed via Komodo with `[[VAR]]` interpolation for secrets.

**How to apply:** Use `km execute deploy-stack git-mcp-siyuan` for all future deploys. The `km list stacks` command fails with a JSON decode error (known Komodo km CLI bug) — use the API directly if listing is needed.

---

## Known Infrastructure Issues

### FerretDB / Komodo Core — Server write persistence bug

`CreateServer` API calls return success with generated OIDs but do NOT persist to FerretDB. This is a silent write failure. Confirmed via MongoDB client showing `Server.countDocuments() = 0` after successful API responses.

**Workaround:** Insert the Server document directly via MongoDB client:
```bash
ssh ubuntu-smurf "docker run --rm --network komodo_default mongo:6 mongosh \
  'mongodb://admin:admin@ferretdb:27017/komodo' --eval '
db.Server.insertOne({
  name: \"ubuntu-smurf-mirror\",
  description: \"\",
  template: false,
  tags: [],
  info: { attempted_public_key: \"\", public_key: \"\" },
  config: {
    address: \"http://100.118.241.89:8120\",
    insecure_tls: true,
    external_address: \"\",
    region: \"\",
    enabled: true,
    auto_rotate_keys: false,
    passkey: \"HRopQo7eC.R9wtNWs\",
    ignore_mounts: [],
    auto_prune: true,
    links: [],
    stats_monitoring: true,
    send_unreachable_alerts: true, send_cpu_alerts: true,
    send_mem_alerts: true, send_disk_alerts: true,
    send_version_mismatch_alerts: true,
    cpu_warning: 90.0, cpu_critical: 99.0,
    mem_warning: 75.0, mem_critical: 95.0,
    disk_warning: 75.0, disk_critical: 95.0,
    maintenance_windows: []
  },
  base_permission: \"None\",
  updated_at: NumberLong(\"1774040000000\")
});'"
```

Then restart Komodo Core: `ssh ubuntu-smurf "docker restart komodo-core-1"`

### Komodo Core in-memory cache

Komodo Core uses an in-memory resource cache loaded from FerretDB on startup. The `CreateServer` API writes to cache AND FerretDB, but the FerretDB write silently fails. Directly inserted FerretDB documents ARE loaded on restart.

After any direct FerretDB modification, restart Core to reload: `ssh ubuntu-smurf "docker restart komodo-core-1"`

### Stack server_id must be set by name (not OID) in FerretDB

When directly modifying stack documents in FerretDB, set `config.server_id` to the server **name** (e.g., `"ubuntu-smurf-mirror"`), not the OID. Komodo resolves this field by name on load.

### Komodo Admin API key — ListServers returns empty

The admin API key returns empty from `ListServers` even though the admin user is `super_admin: true`. Direct `GetServer` by name works. This is a Komodo permission model quirk — `"all": {}` does not grant list access to resources with `base_permission: "None"`.

### ResourceSync "commit-sync" error

`commit-sync` fails with "Cannot commit to sync. Enabled 'managed' mode." when `managed=true` on the sync. This error is expected — `commit-sync` is for writing UI changes back to the repo file, not for applying TOML changes. Use `run-sync` for inbound syncs.

### komodo.toml git_account issue

`komodo.toml` specifies `git_account = "CaseyRo"` but Komodo has no GitHub token stored for this account. Since the repo is public, remove `git_account` from `komodo.toml` in the repo. The field was cleared on the live stack via `km update stack git-mcp-siyuan "git_account=" -y`.

---

## Infrastructure Details

- **Komodo Core**: `ubuntu-smurf:9120`, container `komodo-core-1`
- **FerretDB**: `ferretdb:27017` on the `komodo_default` network, backed by `komodo-postgres-1`
- **Periphery on ubuntu-smurf-mirror**: host network, port 8120, passkey `HRopQo7eC.R9wtNWs`
- **Periphery on ubuntu-smurf**: container `komodo-periphery-1`, port 8120
- **Tailscale IP of ubuntu-smurf-mirror**: 100.118.241.89

## Querying FerretDB directly

```bash
ssh ubuntu-smurf "docker run --rm --network komodo_default mongo:6 mongosh \
  'mongodb://admin:admin@ferretdb:27017/komodo' --eval '<JS_COMMAND>'"
```

Do NOT query Postgres directly using the `documentdb_api.collection()` function — it crashes the Postgres process.
