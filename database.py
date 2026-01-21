"""
Compatibility shim.

Historically the project imported `database` from the repo root.
Redirects to Notion adapter.
"""

from db.notion_adapter import * 

