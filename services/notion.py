import requests
import sys
import re
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path to allow importing config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings

POOLS_DATABASE_ID = "67adabecde574aae99ae7bcbf992a2da"
WHITELIST_DATABASE_ID = "2efe395e228180579172ed23fc480656"

headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {settings.notion_api_key}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}


def extract_property_value(property_data: Dict[str, Any], property_type: str) -> Any:
    """Extract value from a Notion property based on its type."""
    if property_type == "title":
        title_parts = property_data.get("title", [])
        if title_parts:
            return "".join([part.get("plain_text", "") for part in title_parts])
        return ""
    elif property_type == "unique_id":
        unique_id_data = property_data.get("unique_id", {})
        number = unique_id_data.get("number")
        prefix = unique_id_data.get("prefix")
        if prefix:
            return f"{prefix}-{number}" if number else prefix
        return str(number) if number else ""
    elif property_type == "relation":
        relation_data = property_data.get("relation", [])
        # Return list of relation IDs
        return [rel.get("id") for rel in relation_data]
    else:
        return None


def query_database_pages(database_id: str = None) -> List[Dict[str, Any]]:
    """Query all pages from a Notion database."""
    if database_id is None:
        database_id = POOLS_DATABASE_ID
    
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    
    all_pages = []
    has_more = True
    start_cursor = None
    
    while has_more:
        payload = {}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        all_pages.extend(data.get("results", []))
        
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    
    return all_pages


def get_whitelist_data() -> List[Dict[str, Any]]:
    """Get cleaned whitelist data with only username and user_id columns."""
    pages = query_database_pages(WHITELIST_DATABASE_ID)

    def _to_text(prop: Dict[str, Any] | None) -> str:
        """Best-effort conversion of a Notion property to text."""
        if not prop:
            return ""

        prop_type = prop.get("type")

        if prop_type == "title":
            parts = prop.get("title", [])
            return "".join([p.get("plain_text", "") for p in parts])

        if prop_type == "rich_text":
            parts = prop.get("rich_text", [])
            return "".join([p.get("plain_text", "") for p in parts])

        if prop_type == "number":
            value = prop.get("number")
            return "" if value is None else str(value)

        if prop_type == "email":
            return prop.get("email") or ""

        if prop_type == "phone_number":
            return prop.get("phone_number") or ""

        if prop_type == "url":
            return prop.get("url") or ""

        return ""

    cleaned: List[Dict[str, Any]] = []
    for page in pages:
        props = page.get("properties", {})

        # Try common casing variants for property names
        username_prop = (
            props.get("username")
            or props.get("Username")
            or props.get("user_name")
            or props.get("User Name")
        )
        user_id_prop = (
            props.get("user_id")
            or props.get("User ID")
            or props.get("User_Id")
            or props.get("UserId")
        )

        username = _to_text(username_prop)
        user_id_text = _to_text(user_id_prop)
        
        # Convert user_id to int if possible
        try:
            user_id = int(user_id_text) if user_id_text else None
        except ValueError:
            user_id = None
        
        if user_id is not None:
            cleaned.append({
                "username": username,
                "user_id": user_id,
            })

    return cleaned


def parse_balancer_url(url: str) -> Dict[str, str] | None:
    """Parse a Balancer pool URL to extract blockchain, version, and pool address."""
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip()
    strict_pattern = r'https?://balancer\.fi/pools/([^/]+)/([^/]+)/(0x[a-fA-F0-9]{40})'
    match = re.search(strict_pattern, url)
    
    if match:
        return {
            "blockchain": match.group(1).lower(),
            "version": match.group(2).lower(),
            "address": match.group(3).lower(),
            "url": url
        }
    
    # Fallback: find address and infer blockchain/version
    addr_match = re.search(r'0x[a-fA-F0-9]{40}', url)
    if addr_match:
        address = addr_match.group(0).lower()
        try:
            path = url.split('://', 1)[-1].split('/', 1)[-1]
            segments = path.split('/')
            if "pools" in segments:
                idx = segments.index("pools")
                blockchain = segments[idx + 1].lower() if len(segments) > idx + 1 else "ethereum"
                version = segments[idx + 2].lower() if len(segments) > idx + 2 else "v2"
            else:
                blockchain, version = "ethereum", "v2"
        except Exception:
            blockchain, version = "ethereum", "v2"
        
        return {"blockchain": blockchain, "version": version, "address": address, "url": url}
    
    return None


def _extract_pools_from_property(pool_addresses_prop: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract pool URLs from a Notion property and parse them."""
    if not pool_addresses_prop:
        return []
    
    prop_type = pool_addresses_prop.get("type", "")
    urls = []
    
    if prop_type == "rollup":
        rollup_data = pool_addresses_prop.get("rollup", {})
        if rollup_data.get("type") == "array":
            array_items = rollup_data.get("array", [])
            for item in array_items:
                if isinstance(item, dict) and item.get("type") == "url":
                    url_value = item.get("url", "")
                    if url_value:
                        urls.append(url_value)
    elif prop_type == "rich_text":
        rich_text_parts = pool_addresses_prop.get("rich_text", [])
        if rich_text_parts:
            text = "".join([p.get("plain_text", "") for p in rich_text_parts])
            if text:
                urls = [a.strip() for a in text.replace("\n", ",").split(",") if a.strip()]
    elif prop_type == "url":
        url_value = pool_addresses_prop.get("url", "")
        if url_value:
            urls = [url_value]
    
    pools = []
    for url in urls:
        if url and isinstance(url, str):
            parsed = parse_balancer_url(url)
            if parsed:
                pools.append(parsed)
    
    return pools


def get_clients_data() -> List[Dict[str, Any]]:
    """Get all clients with their parsed pool data."""
    pages = query_database_pages(POOLS_DATABASE_ID)
    clients = []
    
    for page in pages:
        properties = page.get("properties", {})
        
        id_prop = properties.get("ID", {})
        record_id = extract_property_value(id_prop, "unique_id")
        
        name_prop = properties.get("Name", {})
        name = extract_property_value(name_prop, "title")
        client_key = name.lower().strip() if name else ""
        
        pool_addresses_prop = (
            properties.get("Pool addresses")
            or properties.get("Pool Addresses")
            or properties.get("pool_addresses")
        )
        
        pools = _extract_pools_from_property(pool_addresses_prop)
        
        clients.append({
            "id": record_id,
            "name": name,
            "client_key": client_key,
            "pools": pools
        })
    
    return clients


def get_client_by_key(client_key: str) -> Dict[str, Any] | None:
    """Find a client by normalized client_key (case-insensitive)."""
    normalized_key = client_key.lower().strip()
    clients = get_clients_data()
    
    for client in clients:
        if client["client_key"] == normalized_key:
            return client
    
    return None


def get_all_clients() -> List[Dict[str, Any]]:
    """Get all clients with their pools."""
    return get_clients_data()


def get_user_by_id(user_id: int) -> Dict[str, Any] | None:
    """Get user data from whitelist by user_id."""
    whitelist = get_whitelist_data()
    for user in whitelist:
        # Convert user_id to int for comparison (it might be string from Notion)
        try:
            if int(user.get("user_id")) == user_id:
                return user
        except (ValueError, TypeError):
            continue
    return None

if __name__ == "__main__":
    pass
