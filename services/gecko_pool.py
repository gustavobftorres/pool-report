"""
Get pool address for a token via GeckoTerminal Top Pools.
One API call per (chain, token); filters by protocol/DEX for per-project addresses.
"""
from __future__ import annotations

import re
import httpx
from typing import Any, Dict, List, Optional

from config import settings

# DefiLlama chain name -> GeckoTerminal network_id
CHAIN_TO_NETWORK = {
    "ethereum": "eth",
    "arbitrum": "arbitrum",
    "polygon": "polygon_pos",
    "base": "base",
    "optimism": "optimism",
    "avalanche": "avax",
    "bsc": "bsc",
    "gnosis": "xdai",
    "fantom": "ftm",
    "celo": "celo",
}

# DefiLlama project -> GeckoTerminal dex ID patterns (for filtering)
DEX_PROTOCOL_MAPPING: Dict[str, List[str]] = {
    "uniswap-v3": ["uniswap_v3", "uniswap-v3"],
    "uniswap-v2": ["uniswap_v2", "uniswap-v2"],
    "uniswap-v4": ["uniswap_v4", "uniswap-v4"],
    "curve-dex": ["curve", "curve.fi", "curve-ethereum"],
    "curve": ["curve", "curve.fi", "curve-ethereum"],
    "balancer": ["balancer", "balancer_v2", "balancer_ethereum", "balancer-ethereum"],
    "balancer-v3": ["balancer-v3", "balancer_v3", "balancer-v3-base", "balancer-v3-plasma"],
    "balancer_v3": ["balancer-v3", "balancer_v3", "balancer-v3-base", "balancer-v3-plasma"],
    "sushiswap": ["sushiswap", "sushi", "sushiswap_v2"],
    "pancakeswap": ["pancakeswap", "pancake_swap", "pancake"],
    "fluid": ["fluid", "fluidfi", "fluid-ethereum"],
}

# Big DEXes used as fallback for lending pools (underlying token liquidity)
BIG_DEXES: List[str] = ["curve", "balancer", "uniswap", "fluid"]

def _normalize_protocol(protocol: str) -> str:
    """Normalize protocol name for lookup (lowercase, strip, spaces -> hyphens)."""
    return (protocol or "").lower().strip().replace(" ", "-")


def is_resolvable_protocol(protocol: str) -> bool:
    """True if we can resolve pool address (DEX or lending fallback to big DEXes)."""
    key = _normalize_protocol(protocol)
    return key in DEX_PROTOCOL_MAPPING or key in LENDING_PROTOCOLS


# Skip these - GeckoTerminal has no lending pools
LENDING_PROTOCOLS = frozenset([
    "aave-v3", "aave-v2", "aave", "compound-v3", "compound-v2", "compound",
    "spark-savings", "spark", "fluid-lending", "morpho-v1", "morpho", "merkl", "maple", "veda",
])


def _extract_address(pool_data: Dict[str, Any]) -> Optional[str]:
    """Extract pool address from GeckoTerminal pool object."""
    addr = (pool_data.get("attributes") or {}).get("address")
    if addr:
        return addr.lower()
    pid = pool_data.get("id", "")
    if "_" in pid:
        return pid.split("_", 1)[1].lower()
    return None


def _get_dex_id(pool_data: Dict[str, Any]) -> str:
    """Get GeckoTerminal dex ID from pool relationships."""
    rel = pool_data.get("relationships", {})
    dex_data = (rel.get("dex") or {}).get("data")
    if dex_data:
        return (dex_data.get("id") or "").lower()
    attrs = pool_data.get("attributes", {})
    return (attrs.get("dex") or attrs.get("exchange_name") or "").lower()


def _parse_fee_from_pool_name(name: Optional[str]) -> Optional[float]:
    """Extract fee percentage from pool name (e.g. 'WETH / USDC 0.05%' -> 0.05)."""
    if not name:
        return None
    m = re.search(r"(\d+\.?\d*)\s*%", name)
    return float(m.group(1)) if m else None


def fetch_pools_for_token_gecko_only(
    chain: str, token_address: str
) -> List[Dict[str, Any]]:
    """
    Fetch all DEX pools for a token from GeckoTerminal (GeckoTerminal-only, no DefiLlama).
    GET /networks/{network}/tokens/{token_address}/pools
    Returns list of pool dicts with: protocol, chain, symbol, pool_address, volume, fees,
    liquidity, dex. All pools have pool_address - no empty rows.
    """
    network = CHAIN_TO_NETWORK.get((chain or "").lower().strip())
    if not network or not token_address or not str(token_address).startswith("0x"):
        return []
    token_address = str(token_address).lower()
    base = settings.gecko_base_url.rstrip("/")
    url = f"{base}/networks/{network}/tokens/{token_address}/pools"
    result: List[Dict[str, Any]] = []
    try:
        r = httpx.get(url, params={"page": 1}, timeout=getattr(settings, "dex_benchmark_timeout", 10.0))
        r.raise_for_status()
        items = r.json().get("data") or []
        network_chain = chain  # Keep original chain for display
        for item in items:
            attrs = item.get("attributes") or {}
            addr = (attrs.get("address") or "").lower()
            if not addr:
                pid = item.get("id", "")
                if "_" in pid:
                    addr = pid.split("_", 1)[1].lower()
            if not addr:
                continue
            name = attrs.get("name") or ""
            volume_usd = attrs.get("volume_usd") or {}
            volume_h24 = float(volume_usd.get("h24") or 0)
            reserve_usd = attrs.get("reserve_in_usd")
            liquidity = float(reserve_usd) if reserve_usd is not None else None
            rels = item.get("relationships") or {}
            dex_data = (rels.get("dex") or {}).get("data") or {}
            dex = dex_data.get("id") or None
            fee_pct = _parse_fee_from_pool_name(name)
            fees = volume_h24 * (fee_pct / 100) if volume_h24 and fee_pct else None
            fdv_raw = attrs.get("fdv_usd")
            mcap_raw = attrs.get("market_cap_usd")
            token_price_raw = attrs.get("token_price_usd")
            fdv_usd = float(fdv_raw) if fdv_raw is not None else None
            market_cap_usd = float(mcap_raw) if mcap_raw is not None else None
            price_usd = float(token_price_raw) if token_price_raw is not None else None
            result.append({
                "protocol": dex,
                "chain": network_chain,
                "symbol": name,
                "pool_address": addr,
                "volume": volume_h24 if volume_h24 else None,
                "fees": fees,
                "liquidity": liquidity,
                "dex": dex,
                "tvl_usd": liquidity,
                "fdv_usd": fdv_usd,
                "market_cap_usd": market_cap_usd,
                "price_usd": price_usd,
            })
        result.sort(key=lambda x: (x.get("volume") or 0), reverse=True)
        return result
    except Exception:
        return []


def fetch_pools(chain: str, token_address: str) -> List[Dict[str, Any]]:
    """
    Fetch all pools for a token from GeckoTerminal (one API call).
    Returns list of pool objects.
    """
    network = CHAIN_TO_NETWORK.get((chain or "").lower().strip())
    if not network or not token_address or not str(token_address).startswith("0x"):
        return []
    token_address = str(token_address).lower()
    base = settings.gecko_base_url.rstrip("/")
    url = f"{base}/networks/{network}/tokens/{token_address}/pools"
    try:
        r = httpx.get(url, params={"page": 1}, timeout=getattr(settings, "dex_benchmark_timeout", 10.0))
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        return []


def get_pool_address_for_big_dex(pools: List[Dict[str, Any]]) -> Optional[str]:
    """
    Find pool address from one of the big DEXes (curve, balancer, uniswap, fluid).
    Used as fallback for lending pools - underlying token liquidity lives on these DEXes.
    Returns first pool whose dex matches any big DEX (pools are ranked by liquidity).
    """
    for p in pools:
        dex_id = _get_dex_id(p)
        for big_dex in BIG_DEXES:
            if big_dex in dex_id or dex_id in big_dex:
                addr = _extract_address(p)
                if addr:
                    return addr
                break
    return None


def fetch_pool_by_address(chain: str, pool_address: str) -> Optional[Dict[str, Any]]:
    """
    Fetch pool details by address from GeckoTerminal.
    GET /networks/{network}/pools/{pool_address}

    Returns dict with volume, fees, liquidity, dex; or None on error.
    Fees = volume_usd.h24 * (pool_fee_percentage / 100).
    """
    network = CHAIN_TO_NETWORK.get((chain or "").lower().strip())
    if not network or not pool_address or not str(pool_address).startswith("0x"):
        return None
    pool_address = str(pool_address).lower()
    base = settings.gecko_base_url.rstrip("/")
    url = f"{base}/networks/{network}/pools/{pool_address}"
    try:
        r = httpx.get(url, timeout=getattr(settings, "dex_benchmark_timeout", 10.0))
        r.raise_for_status()
        data = r.json().get("data")
        if not data:
            return None
        attrs = data.get("attributes") or {}
        rels = data.get("relationships") or {}
        volume_usd = attrs.get("volume_usd") or {}
        volume_h24 = float(volume_usd.get("h24") or 0)
        pool_fee_pct = float(attrs.get("pool_fee_percentage") or 0)
        reserve_usd = attrs.get("reserve_in_usd")
        liquidity = float(reserve_usd) if reserve_usd is not None else None
        dex_data = (rels.get("dex") or {}).get("data") or {}
        dex = dex_data.get("id") or None
        fees = volume_h24 * (pool_fee_pct / 100) if volume_h24 and pool_fee_pct else None
        return {
            "volume": volume_h24 if volume_h24 else None,
            "fees": fees,
            "liquidity": liquidity,
            "dex": dex,
        }
    except Exception:
        return None


def fetch_pools_multi(chain: str, addresses: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch multiple pools by address in one API call.
    GET /networks/{network}/pools/multi/{addresses}
    Returns dict mapping pool_address -> {volume, fees, liquidity, dex}.
    """
    network = CHAIN_TO_NETWORK.get((chain or "").lower().strip())
    if not network or not addresses:
        return {}
    addrs = [str(a).lower() for a in addresses if str(a).startswith("0x")]
    if not addrs:
        return {}
    base = settings.gecko_base_url.rstrip("/")
    url = f"{base}/networks/{network}/pools/multi/{','.join(addrs)}"
    result: Dict[str, Dict[str, Any]] = {}
    try:
        r = httpx.get(url, timeout=getattr(settings, "dex_benchmark_timeout", 10.0))
        r.raise_for_status()
        items = r.json().get("data") or []
        for item in items:
            attrs = item.get("attributes") or {}
            addr = (attrs.get("address") or "").lower()
            if not addr:
                pid = item.get("id", "")
                if "_" in pid:
                    addr = pid.split("_", 1)[1].lower()
            if not addr:
                continue
            volume_usd = attrs.get("volume_usd") or {}
            volume_h24 = float(volume_usd.get("h24") or 0)
            pool_fee_pct = float(attrs.get("pool_fee_percentage") or 0)
            reserve_usd = attrs.get("reserve_in_usd")
            liquidity = float(reserve_usd) if reserve_usd is not None else None
            rels = item.get("relationships") or {}
            dex_data = (rels.get("dex") or {}).get("data") or {}
            dex = dex_data.get("id") or None
            fees = volume_h24 * (pool_fee_pct / 100) if volume_h24 and pool_fee_pct else None
            result[addr] = {
                "volume": volume_h24 if volume_h24 else None,
                "fees": fees,
                "liquidity": liquidity,
                "dex": dex,
            }
        return result
    except Exception:
        return {}


def get_pool_address_for_protocol(
    pools: List[Dict[str, Any]], protocol: str
) -> Optional[str]:
    """
    Find pool address matching the given DefiLlama protocol.
    Returns first pool whose dex matches the protocol's GeckoTerminal patterns.
    For lending protocols, falls back to big DEXes (curve, balancer, uniswap, fluid).
    """
    protocol = _normalize_protocol(protocol)
    if protocol in LENDING_PROTOCOLS:
        return get_pool_address_for_big_dex(pools)
    patterns = DEX_PROTOCOL_MAPPING.get(protocol, [])
    if not patterns:
        return None
    for p in pools:
        dex_id = _get_dex_id(p)
        for pat in patterns:
            if pat in dex_id or dex_id in pat:
                addr = _extract_address(p)
                if addr:
                    return addr
                break
    return None
