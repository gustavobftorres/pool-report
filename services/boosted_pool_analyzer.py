"""
Boosted Pool Analyzer service for detecting and resolving ERC-4626 tokens.

## Research Findings: Boosted Pool Structure

### What Are Boosted Pools?
Boosted pools are Balancer pools that contain wrapped yield-bearing tokens (ERC-4626 vaults)
instead of regular ERC-20 tokens. These pools allow liquidity providers to earn additional
yield from protocols like Aave while providing liquidity.

### API Response Patterns (Based on Research)

#### Boosted Pool Example (bb-a-USD):
- **Type:** "StablePhantom" or "ComposableStable"
- **Name:** Contains "Boosted" keyword or "bb-" prefix
- **Tokens:** Contains nested pool tokens (bb-a-USDC, bb-a-DAI, bb-a-USDT)
- **Structure:** Parent pool contains child linear pools

#### Linear Pool Example (bb-a-USDC):
- **Type:** "AaveLinear" or contains "Linear"
- **Tokens:** Contains 3 tokens:
  1. BPT token (bb-a-USDC itself)
  2. Regular token (USDC)
  3. Wrapped token (aUSDC - Aave wrapped USDC)

#### Regular Pool Example (20wstETH-80AAVE):
- **Type:** "Weighted" or "Stable"
- **Tokens:** Contains regular ERC-20 tokens only
- **No nested structure**

### Key Insights for Detection:
1. Pool type contains: "StablePhantom", "ComposableStable", "AaveLinear", "Boosted"
2. Pool name starts with "bb-" or contains "Boosted"
3. Tokens have symbols starting with "bb-" or ending with wrapped token patterns (aToken, stToken)
4. For competitor search, we need the underlying tokens (USDC, DAI) not wrapped (aUSDC, aDAI)

### Known Wrapped Token Patterns:
- Aave: aUSDC, aDAI, aUSDT (prefix 'a')
- Lido: stETH, wstETH (prefix 'st' or 'wst')
- Balancer Linear Pools: bb-a-USDC, bb-a-DAI (prefix 'bb-')

### References:
- Balancer V2 Boosted Pools: https://docs.balancer.fi/
- ERC-4626 Standard: https://eips.ethereum.org/EIPS/eip-4626
- Tested pools:
  - bb-a-USD: 0x7b50775383d3d6f0215a8f290f2c9e2eebbeceb2
  - bb-a-USDC: 0x9210f1204b5a24742eba12f710636d76240df3d0
"""


# Known wrapped token → underlying token mappings (Ethereum mainnet)
# Addresses are lowercase for case-insensitive matching
WRAPPED_TOKEN_MAP = {
    # Aave aTokens → underlying
    "0xbcca60bb61934080951369a648fb03df4f96263c": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # aUSDC → USDC
    "0x028171bca77440897b824ca71d1c56cac55b68a3": "0x6b175474e89094c44da98b954eedeac495271d0f",  # aDAI → DAI
    "0x3ed3b47dd13ec9a98b44e6204a523e766b225811": "0xdac17f958d2ee523a2206206994597c13d831ec7",  # aUSDT → USDT
    
    # Wrapped Aave tokens (from linear pools)
    "0xd093fa4fb80d09bb30817fdcd442d4d02ed3e5de": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # Wrapped aUSDC → USDC
    
    # Lido staked ETH → WETH
    "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # stETH → WETH
    "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # wstETH → WETH
}

# Symbol mapping for tokens not in address map
WRAPPED_SYMBOL_TO_UNDERLYING = {
    # Aave tokens
    "aUSDC": "USDC",
    "aDAI": "DAI",
    "aUSDT": "USDT",
    "aWETH": "WETH",
    "aWBTC": "WBTC",
    
    # Lido
    "stETH": "WETH",
    "wstETH": "WETH",
    "WSTETH": "WETH",  # Uppercase variant
    "STETH": "WETH",  # Uppercase variant
    
    # Compound
    "cUSDC": "USDC",
    "cDAI": "DAI",
    
    # Wrapped Aave (from linear pools)
    "waUSDC": "USDC",
    "waDAI": "DAI",
    "waUSDT": "USDT",
}

# Boosted pool type indicators
BOOSTED_POOL_TYPES = {
    "StablePhantom",
    "ComposableStable",
    "AaveLinear",
    "EulerLinear",
    "GearboxLinear",
    "YearnLinear",
    "Boosted",
}


def is_pool_boosted(pool_data: dict) -> bool:
    """
    Determine if a Balancer pool is a boosted pool (uses ERC-4626 tokens).
    
    Boosted pools contain wrapped yield-bearing tokens (e.g., aUSDC, stETH)
    instead of regular tokens. This detection is critical for proper competitor
    search, as GeckoTerminal doesn't recognize wrapped tokens.
    
    Detection logic (priority order):
    1. Check API tags field for "BOOSTED" indicator (V3 API only - most reliable)
    2. Fallback: Check pool type for boosted indicators (StablePhantom, AaveLinear, etc.)
    3. Fallback: Check pool name for "bb-" prefix or "Boosted" keyword
    4. Fallback: Check if tokens have nested pool structure (linear pools)
    
    Args:
        pool_data: Pool data dictionary from BalancerAPI
        
    Returns:
        True if pool is boosted, False otherwise
        
    Example:
        >>> pool = await api.get_current_pool_data('0x85b2...')
        >>> is_boosted = is_pool_boosted(pool)
        >>> print(f"Boosted: {is_boosted}")  # True
    """
    if not pool_data or not isinstance(pool_data, dict):
        return False
    
    # PRIORITY 1: Check tags field (most reliable - V3 API)
    tags = pool_data.get("tags", [])
    if tags and isinstance(tags, list):
        for tag in tags:
            tag_upper = str(tag).upper()
            if "BOOSTED" in tag_upper:
                print(f"   ✅ Boosted pool detected via tags: {tags}")
                return True
    
    # PRIORITY 2: Fallback to heuristic detection
    # (For V2 pools or if tags field is missing/empty)
    
    # Check 1: Pool type field
    pool_type = pool_data.get("type", "").strip()
    if pool_type in BOOSTED_POOL_TYPES:
        print(f"   ✅ Boosted pool detected via type: {pool_type}")
        return True
    
    # Check for partial matches in type (e.g., "Linear" in type name)
    if any(indicator.lower() in pool_type.lower() for indicator in ["linear", "boosted", "phantom"]):
        print(f"   ✅ Boosted pool detected via type keyword: {pool_type}")
        return True
    
    # Check 2: Pool name
    pool_name = pool_data.get("name", "").strip()
    if pool_name.startswith("bb-") or "Boosted" in pool_name:
        print(f"   ✅ Boosted pool detected via name: {pool_name}")
        return True
    
    # Check 3: Check if any tokens are from linear/nested pools
    # Linear pool tokens typically have "bb-" prefix in symbol
    tokens = pool_data.get("allTokens", [])
    for token in tokens:
        symbol = token.get("symbol", "")
        if symbol.startswith("bb-"):
            print(f"   ✅ Boosted pool detected via token symbol: {symbol}")
            return True
    
    return False


def get_boosted_pool_type(pool_data: dict) -> str:
    """
    Get specific boosted pool type from API tags or heuristics.
    
    Returns the protocol/type of boosted pool for display purposes.
    
    Args:
        pool_data: Pool data dictionary from BalancerAPI
        
    Returns:
        Boosted pool type string:
        - "AAVE" - Aave boosted pool
        - "EULER" - Euler boosted pool
        - "YEARN" - Yearn boosted pool
        - "GEARBOX" - Gearbox boosted pool
        - "BOOSTED" - Generic boosted pool (type unknown)
        - "" (empty string) - Not a boosted pool
        
    Example:
        >>> pool = await api.get_current_pool_data('0x85b2...')
        >>> boosted_type = get_boosted_pool_type(pool)
        >>> print(boosted_type)  # "AAVE"
    """
    if not is_pool_boosted(pool_data):
        return ""
    
    # Check tags field for specific boosted type
    tags = pool_data.get("tags", [])
    if tags and isinstance(tags, list):
        for tag in tags:
            tag_upper = str(tag).upper()
            
            # Check for specific protocol tags
            if "BOOSTED_AAVE" in tag_upper or "AAVE" in tag_upper:
                return "AAVE"
            elif "BOOSTED_EULER" in tag_upper or "EULER" in tag_upper:
                return "EULER"
            elif "BOOSTED_YEARN" in tag_upper or "YEARN" in tag_upper:
                return "YEARN"
            elif "BOOSTED_GEARBOX" in tag_upper or "GEARBOX" in tag_upper:
                return "GEARBOX"
    
    # Fallback: Check pool type for specific indicators
    pool_type = pool_data.get("type", "").upper()
    pool_name = pool_data.get("name", "").upper()
    
    # Check for protocol names in type or name
    if "AAVE" in pool_type or "AAVE" in pool_name:
        return "AAVE"
    elif "EULER" in pool_type or "EULER" in pool_name:
        return "EULER"
    elif "YEARN" in pool_type or "YEARN" in pool_name:
        return "YEARN"
    elif "GEARBOX" in pool_type or "GEARBOX" in pool_name:
        return "GEARBOX"
    
    # Generic boosted pool (type unknown)
    return "BOOSTED"


def is_100_percent_boosted(pool_data: dict) -> bool:
    """
    Check if a boosted pool contains ONLY wrapped tokens (100% boosted).
    
    A 100% boosted pool should use underlying tokens for competitor search,
    while a partially boosted pool should use the non-wrapped tokens.
    
    Logic:
    1. Get all tokens from pool
    2. Skip BPT tokens (Balancer Pool Tokens - these are LP tokens)
    3. Check if each remaining token is wrapped
    4. Return True only if ALL non-BPT tokens are wrapped
    
    Args:
        pool_data: Pool data dictionary from BalancerAPI
        
    Returns:
        True if all tokens (excluding BPT) are wrapped, False otherwise
        
    Example:
        >>> # Pool with only aUSDC, aDAI
        >>> is_100_percent_boosted(pool_data)  # True
        >>> # Pool with aUSDC and regular USDC
        >>> is_100_percent_boosted(pool_data)  # False
    """
    if not pool_data or not isinstance(pool_data, dict):
        return False
    
    tokens = pool_data.get("allTokens", [])
    if not tokens:
        return False
    
    # Get pool address to identify BPT token
    pool_address = pool_data.get("address", "").lower()
    
    non_bpt_tokens = []
    for token in tokens:
        token_address = token.get("address", "").lower()
        symbol = token.get("symbol", "").upper()
        
        # Skip BPT tokens (pool's own LP token)
        if token_address == pool_address:
            continue
        if "BPT" in symbol or symbol in {"BPT", "BALANCER", "POOL"}:
            continue
        
        non_bpt_tokens.append(token)
    
    # If no non-BPT tokens, not a boosted pool
    if not non_bpt_tokens:
        return False
    
    # Check if ALL non-BPT tokens are wrapped
    all_wrapped = True
    for token in non_bpt_tokens:
        if not _is_token_wrapped(token):
            all_wrapped = False
            break
    
    return all_wrapped


def _is_token_wrapped(token: dict) -> bool:
    """
    Helper function to determine if a token is a wrapped/boosted token.
    
    Args:
        token: Token dictionary with 'address' and 'symbol' fields
        
    Returns:
        True if token is wrapped, False otherwise
    """
    token_address = token.get("address", "").lower()
    symbol = token.get("symbol", "").upper()
    
    # Check if address is in wrapped token map
    if token_address in WRAPPED_TOKEN_MAP:
        return True
    
    # Check if symbol matches wrapped patterns
    if symbol in WRAPPED_SYMBOL_TO_UNDERLYING:
        return True
    
    # Check for common wrapped token prefixes
    wrapped_prefixes = ["A", "C", "BB-", "ST", "WST", "WA"]
    for prefix in wrapped_prefixes:
        if symbol.startswith(prefix) and len(symbol) > len(prefix):
            # Make sure it's not just a token that starts with these letters
            # e.g., "AAVE" is not wrapped, but "aUSDC" is
            if prefix in ["A", "C", "WA"] and symbol in ["AAVE", "COMP", "WETH", "WBTC", "WAVE"]:
                continue
            return True
    
    return False


def get_underlying_tokens(pool_data: dict) -> list[dict]:
    """
    Extract underlying tokens from boosted pool tokens.
    
    Maps wrapped tokens (aUSDC, stETH) to their underlying assets (USDC, ETH).
    This is essential for competitor discovery, as GeckoTerminal recognizes
    underlying tokens but not wrapped versions.
    
    Logic:
    1. For each token in the pool:
       - Skip BPT tokens (pool's own LP token)
       - If token is in WRAPPED_TOKEN_MAP, use mapped underlying address
       - If token symbol matches wrapped pattern, derive underlying symbol
       - If token is already underlying (not wrapped), include it as-is
    2. Return unique list of underlying tokens
    
    Args:
        pool_data: Pool data dictionary from BalancerAPI
        
    Returns:
        List of token dictionaries with 'address' and 'symbol' fields
        
    Example:
        >>> tokens = get_underlying_tokens(pool_data)
        >>> print(tokens)
        [
            {'address': '0xa0b8...', 'symbol': 'USDC'},
            {'address': '0x6b17...', 'symbol': 'DAI'}
        ]
    """
    if not pool_data or not isinstance(pool_data, dict):
        return []
    
    tokens = pool_data.get("allTokens", [])
    if not tokens:
        return []
    
    # Get pool address to identify BPT token
    pool_address = pool_data.get("address", "").lower()
    
    underlying_tokens = []
    seen_addresses = set()
    
    for token in tokens:
        token_address = token.get("address", "").lower()
        symbol = token.get("symbol", "").upper()
        name = token.get("name", "")
        
        # Skip BPT tokens
        if token_address == pool_address:
            continue
        if "BPT" in symbol or symbol in {"BPT", "BALANCER", "POOL"}:
            continue
        
        # Check if this is a wrapped token that needs unwrapping
        if token_address in WRAPPED_TOKEN_MAP:
            # Use mapped underlying address
            underlying_address = WRAPPED_TOKEN_MAP[token_address]
            # Get symbol from mapping, or try to derive it
            if symbol in WRAPPED_SYMBOL_TO_UNDERLYING:
                underlying_symbol = WRAPPED_SYMBOL_TO_UNDERLYING[symbol]
            else:
                # Fallback: strip common prefixes
                underlying_symbol = symbol.lstrip("ABCW")
            
            if underlying_address not in seen_addresses:
                underlying_tokens.append({
                    "address": underlying_address,
                    "symbol": underlying_symbol,
                })
                seen_addresses.add(underlying_address)
        
        elif symbol in WRAPPED_SYMBOL_TO_UNDERLYING:
            # Symbol mapping exists but no address mapping
            # Derive underlying symbol and try to infer address pattern
            underlying_symbol = WRAPPED_SYMBOL_TO_UNDERLYING[symbol]
            
            # Try to find the underlying token in the same pool
            # (Linear pools contain both wrapped and underlying)
            underlying_found = False
            for other_token in tokens:
                other_symbol = other_token.get("symbol", "").upper()
                other_address = other_token.get("address", "").lower()
                if other_symbol == underlying_symbol and other_address not in seen_addresses:
                    underlying_tokens.append({
                        "address": other_address,
                        "symbol": underlying_symbol,
                    })
                    seen_addresses.add(other_address)
                    underlying_found = True
                    break
            
            # If underlying not found in pool, we can't safely map it
            # Skip this token to avoid errors
            if not underlying_found:
                print(f"⚠️  Warning: Could not find underlying token for {symbol}, skipping")
        
        else:
            # This is likely already an underlying token (not wrapped)
            # Include it as-is
            if token_address not in seen_addresses:
                underlying_tokens.append({
                    "address": token_address,
                    "symbol": symbol,
                })
                seen_addresses.add(token_address)
    
    return underlying_tokens
