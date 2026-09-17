"""Unit test suite for GitHub SSH Manager."""

import sys
from pathlib import Path

# Ensure src/ is on sys.path for test discovery across all environments
_src_dir = Path(__file__).resolve().parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
