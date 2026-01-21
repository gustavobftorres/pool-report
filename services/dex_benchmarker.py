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
    ) -> Dict[str, Any]:
        """
        Fetch competitor pools that trade token_a and token_b on the given network.

        Returns a normalized structure with fee range and top pools by 24h volume.
        """
        if not self.enabled:
            return {}

        limit = top_n or self.top_n
        try:
            pools = await self._fetch_pools_for_token(network, token_a)
        except Exception as e:
            logger.warning("DEXBenchmarker: failed to fetch pools for %s: %s", token_a, e)
            return {}

        # Filter pools that contain both tokens
        competitors: List[Dict[str, Any]] = []
        token_b_lower = token_b.lower()
        for p in pools:
            tokens = p.get("tokens", [])
            token_addresses = {t.get("address", "").lower() for t in tokens}
            if token_b_lower in token_addresses:
                competitors.append(self._normalize_pool(p))

        # Sort by 24h volume desc and take top_n
        competitors = sorted(
            competitors, key=lambda x: x.get("volume_24h", 0.0), reverse=True
        )[:limit]

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
        # Visible runtime logging (stdout) so it's easy to confirm we are calling GeckoTerminal
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
                token_lookup[inc.get("id")] = inc.get("attributes", {})

        normalized = []
        for p in pools:
            attrs = p.get("attributes", {})
            rel = p.get("relationships", {})
            token_rels = rel.get("tokens", {}).get("data", []) or []
            tokens = []
            for t in token_rels:
                tid = t.get("id")
                tattrs = token_lookup.get(tid, {})
                tokens.append(
                    {
                        "address": tattrs.get("address", ""),
                        "symbol": tattrs.get("symbol", ""),
                        "name": tattrs.get("name", ""),
                    }
                )

            normalized.append(
                {
                    "id": p.get("id"),
                    "name": attrs.get("name"),
                    "dex": attrs.get("dex") or attrs.get("exchange_name"),
                    "swap_fee": self._safe_float(attrs.get("fee_tier")) or self._safe_float(attrs.get("swap_fee")),
                    "volume_24h": self._safe_float(attrs.get("volume_usd", 0.0))
                    or self._safe_float(attrs.get("volume_24h_usd", 0.0)),
                    "liquidity": self._safe_float(attrs.get("reserve_in_usd", 0.0))
                    or self._safe_float(attrs.get("liquidity_usd", 0.0)),
                    "tokens": tokens,
                }
            )

        return normalized

    def _normalize_pool(self, p: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure required keys exist and types are cleaned."""
        return {
            "name": p.get("name"),
            "dex": p.get("dex"),
            "swap_fee": p.get("swap_fee"),
            "volume_24h": p.get("volume_24h"),
            "liquidity": p.get("liquidity"),
            "tokens": p.get("tokens", []),
        }

    @staticmethod
    def _safe_float(val: Any) -> Optional[float]:
        try:
            if val is None:
                return None
            return float(val)
        except (TypeError, ValueError):
            return None
