## ADDED Requirements

### Requirement: Dockerfile for sidecar container
The system SHALL provide a Dockerfile that builds the mcp-siyuan server as a lightweight container using a Python slim base image. It SHALL install dependencies via uv and set `TRANSPORT=http` as default.

#### Scenario: Docker build succeeds
- **WHEN** `docker build -t mcp-siyuan .` is run
- **THEN** the image builds successfully with all dependencies installed

#### Scenario: Container starts and serves HTTP
- **WHEN** the container starts with default environment
- **THEN** it serves MCP over HTTP on port 8000

### Requirement: docker-compose sidecar configuration
The system SHALL provide a `docker-compose.sidecar.yml` that runs mcp-siyuan alongside SiYuan on a shared bridge network. SiYuan SHALL be reachable at `http://siyuan:6806` from the mcp-siyuan container.

#### Scenario: Sidecar reaches SiYuan
- **WHEN** both containers are running via docker-compose
- **THEN** mcp-siyuan can reach SiYuan's API at `http://siyuan:6806`

### Requirement: Komodo-compatible git deployment
The system SHALL be deployable via Komodo (`km` CLI) git-push workflow. The repo SHALL contain all necessary Docker configuration for Komodo to build and deploy the stack.

#### Scenario: Git push triggers deploy
- **WHEN** code is pushed to the repo's main branch
- **THEN** Komodo picks up the change and rebuilds the sidecar container

### Requirement: Environment variable configuration
The sidecar SHALL read configuration from environment variables: `SIYUAN_URL`, `SIYUAN_TOKEN`, `TRANSPORT`. The docker-compose file SHALL document these with sensible defaults.

#### Scenario: Custom SiYuan URL
- **WHEN** `SIYUAN_URL=http://custom-host:6806` is set
- **THEN** the server connects to SiYuan at that URL instead of the default
