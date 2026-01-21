"""
Notion Database Adapter - Provides SQLAlchemy-like interface using Notion API.

This module mimics the SQLAlchemy models and query interface to allow
existing code to work with Notion instead of Supabase.
"""
from typing import List, Optional, Any
from services.notion import (
    get_whitelist_data,
    get_all_clients,
    get_client_by_key,
    get_user_by_id,
)


class _FieldDescriptor:
    """Descriptor class to mimic SQLAlchemy column attributes."""
    def __init__(self, field_name: str):
        self.field_name = field_name
        self.key = field_name
    
    def __eq__(self, other):
        """Create a comparison object for filtering."""
        return _Comparison(self, other)


class _Comparison:
    """Comparison object for filter conditions."""
    def __init__(self, left, right):
        self.left = left
        self.right = right


class NotionAllowedUser:
    """
    Mimics SQLAlchemy AllowedUser model.
    Represents a whitelisted Telegram user.
    """
    # Class-level descriptors for filter compatibility
    user_id = _FieldDescriptor("user_id")
    username = _FieldDescriptor("username")
    first_name = _FieldDescriptor("first_name")
    last_name = _FieldDescriptor("last_name")
    created_at = _FieldDescriptor("created_at")
    last_seen = _FieldDescriptor("last_seen")
    
    def __init__(self, user_id: int, username: str | None = None):
        self.user_id = user_id
        self.username = username
        self.first_name = None  # Not stored in Notion
        self.last_name = None  # Not stored in Notion
        self.created_at = None  # Not stored in Notion
        self.last_seen = None  # Not stored in Notion (read-only mode)
    
    @classmethod
    def find_by_user_id(cls, user_id: int) -> Optional['NotionAllowedUser']:
        """Find a user by user_id."""
        user_data = get_user_by_id(user_id)
        if user_data:
            return cls(
                user_id=user_data.get("user_id"),
                username=user_data.get("username")
            )
        return None


class NotionClient:
    """
    Mimics SQLAlchemy Client model.
    Represents a client/portfolio grouping (e.g., "aave").
    """
    # Class-level descriptors for filter compatibility
    client_key = _FieldDescriptor("client_key")
    display_name = _FieldDescriptor("display_name")
    created_at = _FieldDescriptor("created_at")
    
    def __init__(self, client_key: str, display_name: str | None = None, pools: List[dict[str, Any]] | None = None):
        self.client_key = client_key
        self.display_name = display_name or client_key
        self.created_at = None  # Not stored in Notion
        self.pools = []  # Will be populated with NotionClientPool objects
        
        # Convert pool objects to NotionClientPool objects
        if pools:
            self.pools = [
                NotionClientPool(
                    client_key=client_key,
                    pool_address=pool.get("address"),
                    blockchain=pool.get("blockchain"),
                    version=pool.get("version"),
                    url=pool.get("url")
                )
                for pool in pools
            ]
    
    @classmethod
    def find_by_key(cls, client_key: str) -> Optional['NotionClient']:
        """Find a client by client_key (case-insensitive)."""
        client_data = get_client_by_key(client_key)
        if client_data:
            return cls(
                client_key=client_data.get("client_key"),
                display_name=client_data.get("name"),
                pools=client_data.get("pools", [])
            )
        return None
    
    @classmethod
    def get_all(cls) -> List['NotionClient']:
        """Get all clients."""
        clients_data = get_all_clients()
        return [
            cls(
                client_key=client.get("client_key"),
                display_name=client.get("name"),
                pools=client.get("pools", [])
            )
            for client in clients_data
        ]


class NotionClientPool:
    """
    Mimics SQLAlchemy ClientPool model.
    Represents a pool address assigned to a client.
    Now includes blockchain and version information.
    """
    # Class-level descriptors for filter compatibility
    id = _FieldDescriptor("id")
    client_key = _FieldDescriptor("client_key")
    pool_address = _FieldDescriptor("pool_address")
    added_at = _FieldDescriptor("added_at")
    
    def __init__(self, client_key: str, pool_address: str, blockchain: str | None = None, version: str | None = None, url: str | None = None):
        self.id = None  # Not needed for Notion
        self.client_key = client_key
        self.pool_address = pool_address
        self.blockchain = blockchain or "ethereum"  # Default to ethereum
        self.version = version or "v2"  # Default to v2
        self.url = url  # Original URL from Notion
        self.added_at = None  # Not stored in Notion


def _extract_filter_field_and_value(condition):
    """Extract field name and value from a SQLAlchemy filter condition."""
    if not (hasattr(condition, 'left') and hasattr(condition, 'right')):
        return None, None
    
    left = condition.left
    right = condition.right
    
    # Extract field name
    field_name = getattr(left, 'key', None) or getattr(left, 'field_name', None) or getattr(left, 'name', None)
    if not field_name:
        left_str = str(left)
        field_name = left_str.split('.')[-1].strip() if '.' in left_str else None
    
    # Extract value
    value = getattr(right, 'value', None) if hasattr(right, '__dict__') else right
    
    return field_name, value


class NotionQuery:
    """Mimics SQLAlchemy query interface for filtering."""
    
    def __init__(self, data: List[Any]):
        self.data = data
    
    def filter(self, *conditions) -> 'NotionQuery':
        """Filter data based on conditions."""
        for condition in conditions:
            if hasattr(condition, 'left') and hasattr(condition, 'right'):
                field_name, value = _extract_filter_field_and_value(condition)
                if field_name and value is not None:
                    self.data = [item for item in self.data if getattr(item, field_name, None) == value]
        return self
    
    def first(self) -> Any | None:
        """Return the first result or None."""
        return self.data[0] if self.data else None
    
    def all(self) -> List[Any]:
        """Return all results."""
        return self.data
    
    def order_by(self, *order_by_clauses) -> 'NotionQuery':
        """Order results (no-op for now)."""
        return self


class NotionSession:
    """Mimics SQLAlchemy Session for compatibility with existing code."""
    
    def query(self, model_class) -> NotionQuery:
        """Create a query for the given model class."""
        if model_class == NotionAllowedUser:
            users_data = get_whitelist_data()
            users = [NotionAllowedUser(user.get("user_id"), user.get("username")) for user in users_data]
            return NotionQuery(users)
        
        elif model_class == NotionClient:
            return NotionQuery(NotionClient.get_all())
        
        elif model_class == NotionClientPool:
            clients = NotionClient.get_all()
            pools = [pool for client in clients for pool in client.pools]
            return NotionQuery(pools)
        
        return NotionQuery([])
    
    def commit(self):
        """No-op for read-only Notion."""
        pass
    
    def add(self, instance):
        """No-op for read-only Notion."""
        pass
    
    def delete(self, instance):
        """No-op for read-only Notion."""
        pass
    
    def close(self):
        """No-op for Notion."""
        pass


def get_notion_db():
    """
    FastAPI dependency: provide a Notion session (compatible with get_db).
    This is a generator function that yields a session and closes it.
    """
    db = NotionSession()
    try:
        yield db
    finally:
        db.close()
