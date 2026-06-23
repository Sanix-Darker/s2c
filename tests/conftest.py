"""Pytest discovery helpers for s2c.

Adding the project root to ``sys.path`` lets tests import ``client``,
``server`` and ``s2c`` directly without any packaging acrobatics. This is
intentional for Phase 1 — at install-time the project layout will be
discovered by ``setuptools`` so this only matters for the in-tree test
runner.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
