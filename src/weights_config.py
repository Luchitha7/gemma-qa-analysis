"""Read and write the scoring weights.

The default weights live in the backend (`FINAL_WEIGHTS` in qa_agent.py) and
never move. This module lets the weights be OVERRIDDEN at runtime by a small
JSON file, so they can be changed from the frontend without editing code.

The rule is simple:
  - if the weights file exists and is valid -> use those weights
  - if it's missing, broken, or incomplete -> fall back to the code defaults

That fallback means the system can never end up with no weights.

    load_weights()          # what the scorer should use right now
    save_weights({...})     # store new weights sent from the frontend
"""

import json
import os

import env_loader

from qa_agent import FINAL_WEIGHTS as DEFAULT_WEIGHTS

WEIGHTS_FILE = os.environ.get("WEIGHTS_FILE_PATH") or os.path.join(os.path.dirname(__file__), "weights.json")

def load_weights():
    """Return the weights to score with right now.

    Starts from the code defaults, then lays any valid saved values on top.
    Anything missing or malformed just keeps its default, so the result is
    always a complete, usable set of weights.
    """
    weights = dict(DEFAULT_WEIGHTS)

    if not os.path.exists(WEIGHTS_FILE):
        return weights

    try:
        with open(WEIGHTS_FILE) as f:
            saved = json.load(f)
    except (json.JSONDecodeError, OSError):
        return weights

    for key in DEFAULT_WEIGHTS:
        value = saved.get(key)
        if isinstance(value, (int, float)):
            weights[key] = float(value)

    return weights

def save_weights(new_weights):
    """Save weights sent from the frontend, and return what was stored.

    We only keep the keys we recognise, and each must be a number; unknown or
    invalid entries are ignored and keep their default. This means a bad or
    partial payload can't corrupt the file.
    """
    weights = dict(DEFAULT_WEIGHTS)
    for key in DEFAULT_WEIGHTS:
        value = new_weights.get(key)
        if isinstance(value, (int, float)):
            weights[key] = float(value)

    with open(WEIGHTS_FILE, "w") as f:
        json.dump(weights, f, indent=2)

    return weights

if __name__ == "__main__":
    print("Code defaults :", DEFAULT_WEIGHTS)
    print("Currently used:", load_weights())
    print("Weights file  :", WEIGHTS_FILE,
          "(exists)" if os.path.exists(WEIGHTS_FILE) else "(not created yet)")
