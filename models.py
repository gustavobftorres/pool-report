"""
Compatibility shim.

Historically the project imported `models` from the repo root.
The implementation now lives in `db.models`.
"""

from db.models import *

