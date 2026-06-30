"""Helpers for freeing local dev ports before starting servers."""

from __future__ import annotations

import os
import subprocess


def free_listening_port(port: int) -> None:
    """Stop processes listening on *port* (Windows dev helper)."""
    if os.name != "nt":
        return

    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    own_pid = str(os.getpid())
    seen: set[str] = set()

    for line in result.stdout.splitlines():
        if "LISTENING" not in line or f":{port}" not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        pid = parts[-1]
        if not pid.isdigit() or pid == own_pid or pid in seen:
            continue
        seen.add(pid)
        subprocess.run(
            ["taskkill", "/F", "/PID", pid],
            capture_output=True,
            check=False,
        )
