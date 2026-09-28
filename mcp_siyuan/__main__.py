"""Allow running as `python -m mcp_siyuan`."""

from mcp_siyuan.server import main

if __name__ == "__main__":  # importing this module must not start the stdio server
    main()
