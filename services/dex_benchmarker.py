"""
GeckoTerminal-based DEX benchmarker.

Fetches competitor pools for a given token pair on a network and normalizes
fee/volume/liquidity so specialists can benchmark Balancer pools.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class DEXBenchmarker:
    """Fetch competitor DEX metrics using GeckoTerminal public API."""

    def __init__(self) -> None:
        self.base_url = settings.gecko_base_url.rstrip("/")
        self.enabled = settings.dex_benchmark_enabled
        self.top_n = settings.dex_benchmark_top_n
        self.timeout = settings.dex_benchmark_timeout

    async def fetch_competitors(
        self,
        network: str,
        token_a: str,
        token_b: str,
        top_n: Optional[int] = None,
        exclude_pool_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch competitor pools that contain token_b (paired with any token) on the given network.
        
        Competitor pools are defined as pools that contain the second token (token_b) paired with
        any other token, not necessarily the exact same pair as the input pool.
        
        Returns a normalized structure with fee range and top pools by 24h volume.
        """
        if not self.enabled:
            return {}

        limit = top_n or self.top_n
        
        # Search for pools containing token_b (e.g., AAVE)
        # This finds all pools where token_b is paired with any other token
        # Competitor pools are defined as pools containing token_b, not necessarily the exact pair
        try:
            pools = await self._fetch_pools_for_token(network, token_b)
        except Exception as e:
            logger.warning("DEXBenchmarker: failed to fetch pools for %s: %s", token_b, e)
            return {}

        # Filter pools: all pools already contain token_b (since we searched by it)
        # Just need to exclude the input pool and sort by volume
        competitors: List[Dict[str, Any]] = []
        exclude_address_lower = exclude_pool_address.lower() if exclude_pool_address else None
        logger.info(f"Finding competitor pools containing token_b: {token_b.lower()}")
        if exclude_address_lower:
            logger.info(f"Excluding input pool address: {exclude_address_lower}")
        logger.info(f"Total pools fetched: {len(pools)}")
        
        for p in pools:
            pool_name = p.get("name", "unknown")
            pool_address = p.get("pool_address", "").lower() if p.get("pool_address") else None
            
            # Skip the input pool itself
            if exclude_address_lower and pool_address == exclude_address_lower:
                logger.info(f"⏭️  Skipping input pool: {pool_name} ({pool_address})")
                continue
            
            # All pools from this search contain token_b, so they're all competitors
            volume_24h = p.get("volume_24h", 0.0) or 0.0
            logger.info(f"✅ Competitor found: {pool_name} (volume_24h: {volume_24h})")
            competitors.append(self._normalize_pool(p))

        # Sort by 24h volume desc and take top_n
        competitors = sorted(
            competitors, key=lambda x: x.get("volume_24h", 0.0) or 0.0, reverse=True
        )[:limit]
        
        logger.info(f"Selected top {len(competitors)} competitors by volume")

        if not competitors:
            return {}

        fees = [c["swap_fee"] for c in competitors if c.get("swap_fee") is not None]
        fee_range = {}
        if fees:
            fees_sorted = sorted(fees)
            mid = len(fees_sorted) // 2
            median = (
                fees_sorted[mid]
                if len(fees_sorted) % 2 == 1
                else (fees_sorted[mid - 1] + fees_sorted[mid]) / 2
            )
            fee_range = {
                "min_fee": fees_sorted[0],
                "median_fee": median,
                "max_fee": fees_sorted[-1],
            }

        total_volume = sum(c.get("volume_24h", 0.0) or 0.0 for c in competitors)

        return {
            "competitors": competitors,
            "fee_range": fee_range,
            "total_volume_24h": total_volume,
        }

    async def _fetch_pools_for_token(self, network: str, token: str) -> List[Dict[str, Any]]:
        """
        Fetch pools for a token via GeckoTerminal:
        GET /api/v2/networks/{network}/tokens/{token}/pools

        Returns raw pool list (dicts).
        """
        url = f"{self.base_url}/networks/{network}/tokens/{token}/pools"
        print(f"🦎 GeckoTerminal GET {url}?page=1")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params={"page": 1})
            if resp.status_code >= 400:
                print(f"🦎 GeckoTerminal status={resp.status_code} body={resp.text[:300]}")
            resp.raise_for_status()
            data = resp.json()

        pools = data.get("data", [])
        included = data.get("included", []) or []

        # Build a quick lookup for token details in 'included'
        token_lookup = {}
        for inc in included:
            if inc.get("type") == "token":
                token_id = inc.get("id")
                token_attrs = inc.get("attributes", {})
                token_lookup[token_id] = token_attrs
                # Log first few tokens to debug
                if len(token_lookup) <= 3:
                    logger.info(f"Token in lookup: {token_id} -> address: {token_attrs.get('address', 'NO ADDRESS')}, symbol: {token_attrs.get('symbol', 'NO SYMBOL')}")
        
        logger.info(f"Built token lookup with {len(token_lookup)} tokens from included array")
        if not token_lookup:
            logger.warning("No tokens found in 'included' array! Token extraction will rely on ID parsing.")

        normalized = []
        for p in pools:
            attrs = p.get("attributes", {})
            rel = p.get("relationships", {})
            
            # GeckoTerminal API uses base_token and quote_token, not tokens
            # Collect all token references
            token_refs = []
            
            # Check for base_token
            base_token_data = rel.get("base_token", {}).get("data")
            if base_token_data:
                token_refs.append(base_token_data)
            
            # Check for quote_token
            quote_token_data = rel.get("quote_token", {}).get("data")
            if quote_token_data:
                token_refs.append(quote_token_data)
            
            # Check for quote_tokens (array, used in some pools like Curve)
            quote_tokens_data = rel.get("quote_tokens", {}).get("data", [])
            if quote_tokens_data:
                token_refs.extend(quote_tokens_data)
            
            # Fallback to old tokens format if present
            if not token_refs:
                token_rels = rel.get("tokens", {}).get("data", []) or []
                token_refs = token_rels
            
            tokens = []
            for t in token_refs:
                tid = t.get("id")
                tattrs = token_lookup.get(tid, {})
                token_address = tattrs.get("address", "")
                token_symbol = tattrs.get("symbol", "")
                
                # Fallback: Extract address from token ID if it's in format "network_0x..."
                if not token_address and isinstance(tid, str) and "_" in tid:
                    parts = tid.split("_", 1)
                    if len(parts) == 2 and parts[1].startswith("0x") and len(parts[1]) == 42:
                        token_address = parts[1].lower()
                        logger.debug(f"Extracted address from token ID: {tid} -> {token_address}")
                
                if not token_address:
                    logger.warning(f"Token {tid} not found in lookup and could not extract address from ID")
                
                tokens.append(
                    {
                        "address": token_address,
                        "symbol": token_symbol,
                        "name": tattrs.get("name", ""),
                    }
                )
            
            # Log token extraction for debugging
            if len(normalized) < 5:
                logger.info(f"Pool {attrs.get('name', 'unknown')}: extracted {len(tokens)} tokens")
                for tok in tokens:
                    logger.info(f"  - {tok.get('symbol', '?')}: {tok.get('address', 'no address')}")
                if not tokens or not any(t.get('address') for t in tokens):
                    logger.warning(f"Pool {attrs.get('name', 'unknown')} has no valid token addresses!")
                    logger.warning(f"  Token refs: {token_refs}")
                    logger.warning(f"  Token lookup keys: {list(token_lookup.keys())[:5]}")

            # Extract pool address from id (format: network_address or network:address) or attributes
            pool_id = p.get("id", "")
            pool_address = None
            
            # Try attributes.address first (most reliable)
            pool_address = attrs.get("address")
            if pool_address and isinstance(pool_address, str) and pool_address.startswith("0x"):
                pool_address = pool_address.lower()
            else:
                # Parse from id field - format can be "eth_0x..." or "eth:0x..."
                if isinstance(pool_id, str):
                    # Try underscore separator first (eth_0x...)
                    if "_" in pool_id:
                        parts = pool_id.split("_", 1)
                        if len(parts) == 2 and parts[1].startswith("0x") and len(parts[1]) == 42:
                            pool_address = parts[1].lower()
                    # Try colon separator (eth:0x...)
                    elif ":" in pool_id:
                        parts = pool_id.split(":", 1)
                        if len(parts) == 2 and parts[1].startswith("0x") and len(parts[1]) == 42:
                            pool_address = parts[1].lower()
                    # If id is already an address
                    elif pool_id.startswith("0x") and len(pool_id) == 42:
                        pool_address = pool_id.lower()
            
            if not pool_address:
                logger.warning(f"Could not extract pool address from pool {pool_id}, attributes: {attrs.get('address')}")

            # Extract DEX from relationships.dex.data.id (e.g., "balancer_ethereum", "uniswap_v3")
            dex_id = None
            dex_data = rel.get("dex", {}).get("data")
            if dex_data:
                dex_id = dex_data.get("id")
            # Fallback to attributes if not in relationships
            if not dex_id:
                dex_id = attrs.get("dex") or attrs.get("exchange_name")

            normalized.append(
                {
                    "id": pool_id,
                    "name": attrs.get("name"),
                    "dex": dex_id,
                    "pool_address": pool_address,  # Include in normalized data
                    "swap_fee": self._safe_float(attrs.get("fee_tier")) or self._safe_float(attrs.get("swap_fee")),
                    "volume_24h": self._safe_float(attrs.get("volume_usd", {}).get("h24", 0.0))
                    or self._safe_float(attrs.get("volume_24h_usd", 0.0)),
                    "liquidity": self._safe_float(attrs.get("reserve_in_usd", 0.0))
                    or self._safe_float(attrs.get("liquidity_usd", 0.0)),
                    "tokens": tokens,
                }
            )

        return normalized

    def _normalize_pool(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure required keys exist and types are cleaned."""
        pool_address = self._extract_pool_address(p)
        dex_normalized = self._normalize_dex_name(p.get("dex"))
        
        return {
            "name": p.get("name"),
            "dex": p.get("dex"),  # Keep original for reference
            "dex_normalized": dex_normalized,  # Normalized for Dune queries
            "pool_address": pool_address,
            "swap_fee": p.get("swap_fee"),
            "volume_24h": p.get("volume_24h"),
            "liquidity": p.get("liquidity"),
            "tokens": p.get("tokens", []),
        }

    @staticmethod
    def _extract_pool_address(pool_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract pool address from GeckoTerminal pool data.
        
        Tries multiple strategies:
        1. Check attributes.address if available
        2. Parse from id field (format: {network}_{address} or {network}:{address})
        3. Fallback to id if it's already an address format
        
        Args:
            pool_data: Pool data dictionary from GeckoTerminal
            
        Returns:
            Pool address (0x...) or None if not found
        """
        # Strategy 1: Check attributes.address
        attrs = pool_data.get("attributes", {})
        if isinstance(attrs, dict):
            address = attrs.get("address")
            if address and isinstance(address, str) and address.startswith("0x"):
                return address.lower()
        
        # Strategy 2: Parse from id field (format: {network}_{address} or {network}:{address})
        pool_id = pool_data.get("id", "")
        if isinstance(pool_id, str):
            # Try underscore separator first (eth_0x...)
            if "_" in pool_id:
                parts = pool_id.split("_", 1)
                if len(parts) == 2 and parts[1].startswith("0x") and len(parts[1]) == 42:
                    return parts[1].lower()
            # Try colon separator (eth:0x...)
            elif ":" in pool_id:
                parts = pool_id.split(":", 1)
                if len(parts) == 2 and parts[1].startswith("0x") and len(parts[1]) == 42:
                    return parts[1].lower()
            # Strategy 3: Check if id is already an address
            elif pool_id.startswith("0x") and len(pool_id) == 42:
                return pool_id.lower()
        
        return None

    @staticmethod
    def _normalize_dex_name(dex: Optional[str]) -> Optional[str]:
        """
        Normalize DEX name from GeckoTerminal to match Dune query mapping.
        
        Maps variations like:
        - uniswap_v3, uniswap_v2 -> UniSwap
        - curve -> Curve
        - pancakeswap, pancake_swap -> PancakeSwap
        - fluid -> Fluid
        - balancer -> Balancer
        
        Args:
            dex: DEX name from GeckoTerminal
            
        Returns:
            Normalized DEX name matching Dune query keys, or None if not recognized
        """
        if not dex:
            return None
        
        dex_lower = dex.lower().strip()
        
        # Mapping of GeckoTerminal DEX names to normalized names
        # GeckoTerminal returns DEX IDs like "fluid-ethereum", "uniswap_v3", "balancer_ethereum", etc.
        dex_mapping = {
            # UniSwap variations
            "uniswap": "UniSwap",
            "uniswap_v2": "UniSwap",
            "uniswap_v3": "UniSwap",
            "uniswap_v4": "UniSwap",
            "uniswap-v2": "UniSwap",
            "uniswap-v3": "UniSwap",
            "uniswap-v4": "UniSwap",
            # Curve
            "curve": "Curve",
            "curve.fi": "Curve",
            "curve-ethereum": "Curve",
            # PancakeSwap
            "pancakeswap": "PancakeSwap",
            "pancake_swap": "PancakeSwap",
            "pancake": "PancakeSwap",
            "pancakeswap-ethereum": "PancakeSwap",
            # Fluid
            "fluid": "Fluid",
            "fluidfi": "Fluid",
            "fluid-ethereum": "Fluid",  # Format from GeckoTerminal API
            # Balancer
            "balancer": "Balancer",
            "balancer_v2": "Balancer",
            "balancer_v3": "Balancer",
            "balancer_ethereum": "Balancer",  # Format from GeckoTerminal API
            "balancer-ethereum": "Balancer",
        }
        
        # Direct match
        if dex_lower in dex_mapping:
            return dex_mapping[dex_lower]
        
        # Partial match (e.g., "uniswap_v3_ethereum" -> "UniSwap")
        for key, value in dex_mapping.items():
            if key in dex_lower:
                return value
        
        # If no match found, try to capitalize first letter of each word
        # This handles cases like "Uniswap V3" -> "UniSwap"
        words = dex_lower.replace("_", " ").replace("-", " ").split()
        if words:
            # Check if first word matches any known DEX
            first_word = words[0]
            for key, value in dex_mapping.items():
                if key.startswith(first_word) or first_word in key:
                    return value
        
        logger.warning(f"Unknown DEX name: {dex}, returning None")
        return None

    @staticmethod
    def _safe_float(val: Any) -> Optional[float]:
        try:
            if val is None:
                return None
            return float(val)
        except (TypeError, ValueError):
            return None
