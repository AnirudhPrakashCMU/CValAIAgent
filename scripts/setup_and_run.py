#!/usr/bin/env python3
"""Setup environment and start MockPilot services."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT / ".env-example"
ENV_FILE = ROOT / ".env"

PLACEHOLDERS = {
    "OPENAI_API_KEY": "your_openai_api_key_here",
    "JWT_SECRET_KEY": "a_very_strong_and_secret_key_please_change_me",
    "MONGODB_URI": "mongodb://user:password@host:port/database?retryWrites=true&w=majority",
}

def prompt(key: str, default: str) -> str:
    value = input(f"{key} [{default}]: ").strip()
    return value or default

def create_env() -> None:
    if ENV_FILE.exists():
        print(".env already exists. Using existing file.")
        return
    lines = []
    for line in ENV_EXAMPLE.read_text().splitlines():
        stripped = line.strip()
        matched = False
        for key, placeholder in PLACEHOLDERS.items():
            if stripped.startswith(f"{key}="):
                val = prompt(key, placeholder)
                lines.append(f"{key}={val}")
                matched = True
                break
        if not matched:
            lines.append(line)
    ENV_FILE.write_text("\n".join(lines))
    print(f"Created {ENV_FILE}")

def run(cmd: list[str]) -> None:
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def main() -> None:
    create_env()
    run(["make", "bootstrap"])
    run(["make", "dev"])

if __name__ == "__main__":
    main()
