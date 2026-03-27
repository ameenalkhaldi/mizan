"""
MCP Server for Arabic Morphological Analysis (صرف)

Wrapper that runs the server from the installed mizan package.
Install first: pip install -e .

For MCP config, point here:
    "command": "/path/to/mizan/.venv/bin/python3",
    "args": ["/path/to/mizan/mcp-server/server.py"]
"""

from mizan.server import main

if __name__ == "__main__":
    main()
