"""Serve the character map and Episode Studio on localhost.

    PYTHONPATH=src python -m mbh.webapp

MBH_HOST defaults to 127.0.0.1 and MBH_PORT to 8765. There is no authentication;
set MBH_HOST only if a trusted proxy is in front of the process.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("MBH_HOST", "127.0.0.1")
    port = int(os.environ.get("MBH_PORT", "8765"))
    uvicorn.run("mbh.webapp.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
