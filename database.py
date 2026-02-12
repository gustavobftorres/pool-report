"""
Compatibility shim.

Historically the project imported `database` from the repo root.
Redirects to Notion adapter.
"""

from notion.notion_adapter import * 