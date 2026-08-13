#!/usr/bin/env python3
"""CI/container entrypoint for immutable model-manifest verification."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.artifact_manifest import verify_model_manifest

if __name__ == "__main__":
    print(json.dumps(verify_model_manifest(), sort_keys=True))
