"""
Compatibility shim.

Historically the project imported `database` from the repo root.
Redirects to Notion adapter.
"""

<<<<<<< HEAD
from db.notion_adapter import * 

=======
from notion.notion_adapter import * 
>>>>>>> @gbr/feat/takeaways
