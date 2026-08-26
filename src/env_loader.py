"""Lightweight, zero-dependency environment loader.

Finds a .env file in the project root or current directory and injects its
variables into os.environ (without overwriting anything already set). Every
module that reads configuration imports this so the .env is loaded no matter
which script is the entry point. Importing it more than once is harmless.
"""

import os


def load_env():
    """Load variables from a .env file into os.environ if not already set."""
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]
    for env_path in candidates:
        if os.path.isfile(env_path):
            try:
                with open(env_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if (v.startswith('"') and v.endswith('"')) or \
                                (v.startswith("'") and v.endswith("'")):
                            v = v[1:-1]
                        if k not in os.environ:
                            os.environ[k] = v
                break
            except Exception:
                pass


load_env()
