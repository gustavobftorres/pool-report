# Developer Guide: Critical Information

This document contains essential information that every developer working on the Balancer Pool Reporter must know. Read this before making changes to the codebase.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Critical Design Decisions](#critical-design-decisions)
3. [Pool Types & Special Handling](#pool-types--special-handling)
4. [API Integration Details](#api-integration-details)
5. [Parameter Change Detection](#parameter-change-detection)
6. [Boosted Pool Detection](#boosted-pool-detection)
7. [Data Export System](#data-export-system)
8. [Common Pitfalls](#common-pitfalls)
9. [Testing Guidelines](#testing-guidelines)
10. [Future Considerations](#future-considerations)

---

## Architecture Overview

### Service Layer Structure

```
services/
├── balancer_api.py           # GraphQL queries to Balancer V2/V3 APIs
├── metrics_calculator.py     # Core metrics calculation and comparison
├── boosted_pool_analyzer.py  # Boosted pool detection and token extraction
├── pool_history_analyzer.py  # Parameter change detection and impact analysis
├── lp_return_calculator.py   # Hold vs Pool profitability analysis
├── data_exporter.py          # Excel/CSV export with multi-format support
├── telegram_sender.py        # Telegram card generation and delivery
├── anchor_token_info.py      # Lending market data from DefiLlama
├── dune_metrics.py           # Dune Analytics integration
└── coingecko_api.py          # Historical price data
```

### Data Flow

```
API Request → Main.py → MetricsCalculator → BalancerAPI → Pool Data
                     ↓
         BoostedPoolAnalyzer (detect + extract underlying tokens)
                     ↓
         PoolHistoryAnalyzer (detect parameter changes)
                     ↓
         LPReturnCalculator (calculate hold vs pool)
                     ↓
         DataExporter (generate Excel/CSV)
                     ↓
         TelegramSender (deliver reports)
```

---

## Critical Design Decisions

### 1. Balancer API Version Handling

**Problem**: Balancer has V2 (subgraph) and V3 (new API) with different data structures.

**Solution**: 
- `balancer_api.py` handles both V2 and V3
- V3 API used as primary source (has `tags` field, better performance)
- Automatic fallback to V2 for older pools
- Chain parameter: `DEFAULT_CHAIN` (MAINNET, ARBITRUM, etc.)

**Developer Must Know**:
- Always check `pool_data.get("version")` to handle version differences
- V3 has `tags` field (array of strings) - V2 does not
- V2 addresses are lowercase, V3 can be mixed case - normalize with `.lower()`

### 2. Pool Address Normalization

**Critical**: Always normalize pool addresses to lowercase before comparison.

```python
# CORRECT
pool_address = pool_address.lower()

# WRONG - will cause lookup failures
if pool_address == "0x3DE27EFA...":  # Mixed case will fail
```

**Why**: Blockchain addresses are case-insensitive, but Python dictionaries are not. Different APIs return different casings.

### 3. Timestamp Handling

**Critical**: Always use UTC timezone for all timestamps.

```python
from datetime import datetime, timezone

# CORRECT
now = datetime.now(timezone.utc)
timestamp = int(now.timestamp())

# WRONG - will cause timezone issues
now = datetime.now()  # Uses local timezone
```

**Why**: Balancer API returns UTC timestamps. Local timezone causes calculation errors.

---

## Pool Types & Special Handling

### Weighted Pools
- **Weight changes**: IMMUTABLE (except LBPs)
- **Detection**: Type contains "Weighted" but NOT "LiquidityBootstrapping"
- **Never track weight changes** for regular weighted pools

### LBP (Liquidity Bootstrapping Pools)
- **Weight changes**: MUTABLE (designed to change over time)
- **Detection**: Type contains "LBP" or "LiquidityBootstrapping"
- **Track weight changes** - this is expected behavior
- **Helper function**: `_is_lbp_pool(pool_type, pool_name)`

### Stable Pools
- **Amp factor**: MUTABLE (can be gradually updated)
- **Events**: `AmpUpdateStarted`, `AmpUpdateStopped`
- **Detection**: Type contains "Stable", "ComposableStable", "MetaStable"
- **Track amp factor changes** for stable pools only

### Stable Surge Pools
- **Surge parameters**: MUTABLE (stored in hook contract)
- **Events**: `SurgeThresholdChanged`, `SurgeFeeChanged`
- **Detection**: Type contains "Surge" OR hook address matches known surge hooks
- **Critical**: Surge parameters are in **hook contracts**, NOT pool contracts
- **Events may not be in subgraph yet** - implementation is future-proof

### Boosted Pools
- **Detection Priority**:
  1. API `tags` field (most reliable) - Phase 8
  2. Pool type (StablePhantom, AaveLinear, etc.)
  3. Pool name (starts with "bb-" or contains "Boosted")
  4. Token symbols (wrapped token indicators)
- **Types**: AAVE, EULER, YEARN, GEARBOX, or generic BOOSTED
- **Token extraction**: 100% boosted pools → extract underlying tokens

---

## API Integration Details

### Balancer V3 API Query Structure

**Critical Fields**:
```graphql
{
  id
  address
  name
  type
  tags              # Phase 8 addition - array of strings
  allTokens {
    address
    symbol
    balance
  }
}
```

**Tags Field** (Phase 8):
- Contains pool categorization: `["BOOSTED_AAVE", "BOOSTED", "INCENTIVIZED"]`
- Used for boosted pool detection
- May be empty array for V2 pools or uncategorized pools
- Always check `if tags and isinstance(tags, list)` before using

### Event Queries

**Available Events**:
- `SwapFeePercentageChanged` - All pool types ✅
- `WeightsGraduallyChanged` - LBP pools only ✅
- `AmpUpdateStarted` - Stable pools ✅
- `AmpUpdateStopped` - Stable pools ✅
- `SurgeThresholdChanged` - Stable Surge pools ⚠️ (may not be indexed yet)
- `SurgeFeeChanged` - Stable Surge pools ⚠️ (may not be indexed yet)

**Event Structure**:
```python
{
    "type": "SwapFeePercentageChanged",
    "timestamp": 1234567890,
    "previousFee": "0.003",
    "swapFeePercentage": "0.0025",
    "blockNumber": 12345678
}
```

---

## Parameter Change Detection

### Filtering Logic (Phase 7)

**Weight Changes**:
```python
# ONLY track for LBP pools
if event_type == "WeightsGraduallyChanged":
    if not _is_lbp_pool(pool_type, pool_name):
        return None  # Skip for regular weighted pools
```

**Amp Factor Changes**:
```python
# ONLY track for stable pools
if event_type in ["AmpUpdateStarted", "AmpUpdateStopped"]:
    if "stable" not in pool_type.lower():
        return None  # Skip for non-stable pools
```

**Surge Parameter Changes**:
```python
# Track for surge pools
# Parameters are in HOOK CONTRACT, not pool contract
if event_type in ["SurgeThresholdChanged", "SurgeFeeChanged"]:
    # Events may not exist in subgraph yet
    # Implementation is future-proof
```

### Impact Analysis

**Methodology**:
1. Fetch metrics 7 days before change
2. Fetch metrics 7 days after change
3. Calculate percentage change for each metric
4. Generate human-readable summary

**Required Data**:
- At least 14 days of snapshot data (7 before + 7 after)
- Snapshots should exist for the date range
- Gracefully handle missing data

---

## Boosted Pool Detection

### Detection Priority (Phase 8)

```python
def is_pool_boosted(pool_data: dict) -> bool:
    # PRIORITY 1: Check tags field (most reliable)
    tags = pool_data.get("tags", [])
    if tags and isinstance(tags, list):
        for tag in tags:
            if "BOOSTED" in tag.upper():
                return True
    
    # PRIORITY 2: Fallback to heuristics
    # (pool type, name, token symbols)
    ...
```

### Boosted Type Extraction (Phase 8)

```python
def get_boosted_pool_type(pool_data: dict) -> str:
    """
    Returns: "AAVE", "EULER", "YEARN", "GEARBOX", "BOOSTED", or ""
    """
    if not is_pool_boosted(pool_data):
        return ""
    
    # Check tags for specific type
    tags = pool_data.get("tags", [])
    if tags:
        if "BOOSTED_AAVE" in str(tags).upper():
            return "AAVE"
        # ... check other types
    
    # Fallback to heuristics (pool name/type)
    ...
```

### Underlying Token Mapping

**Known Mappings**:
```python
WRAPPED_TO_UNDERLYING = {
    "aUSDC": "USDC",    # Aave
    "aDAI": "DAI",      # Aave
    "aUSDT": "USDT",    # Aave
    "wstETH": "ETH",    # Lido
    "stETH": "ETH",     # Lido
    "rETH": "ETH",      # Rocket Pool
    "cbETH": "ETH",     # Coinbase
    # ... see boosted_pool_analyzer.py for full list
}
```

**Adding New Mappings**:
1. Update `WRAPPED_TO_UNDERLYING` dict in `boosted_pool_analyzer.py`
2. Add test case to `test_boosted_pool_analyzer.py`
3. Document in `docs/new_features.md`

---

## Data Export System

### File Naming Convention

**Single Pool**:
```
PoolReport_{pool_address_short}_{token_symbol}_{timestamp}.xlsx
PoolMetrics_{pool_address_short}_{timestamp}.csv
```

**Multi-Pool** (Phase 6):
```
PoolReport_{N}pools_{token_symbol}_{timestamp}.xlsx
PoolMetrics_{N}pools_{timestamp}.csv
```

**Example**:
```
PoolReport_0x3de27efa_USDC_20260212_143022.xlsx
PoolReport_3pools_USDC_20260212_143022.xlsx
```

### Excel Sheet Structure

**Single-Pool (3 tabs)**:
1. `all_metrics` - Flat metric structure
2. `Summary` - High-level stats
3. `Anchor Token` - Anchor token data

**Multi-Pool (4 tabs)** - Phase 6:
1. `Pool Comparison` - Side-by-side comparison (includes Boosted column)
2. `Rankings` - Top 3 by volume, TVL, custom metrics
3. `Summary` - Totals and weighted averages
4. `Anchor Token` - Anchor token data

### Export Methods

```python
from services.data_exporter import DataExporter

exporter = DataExporter()

# Single pool
export_files = exporter.export_simple_pool_metrics(
    pool_metrics=metrics,
    pool_data=pool_data,
    anchor_df=anchor_df,
    format="both"  # or "excel", "csv"
)

# Multi-pool (Phase 6)
export_files = exporter.export_multi_pool_metrics(
    multi_metrics=multi_metrics,
    anchor_df=anchor_df,
    format="both"
)
```

---

## Common Pitfalls

### 1. Not Handling Missing Data

**Problem**: APIs may return incomplete data.

**Solution**: Always use `.get()` with defaults.

```python
# CORRECT
pool_type = pool_data.get("type", "Unknown")
tokens = pool_data.get("allTokens", [])

# WRONG - will crash if key missing
pool_type = pool_data["type"]
```

### 2. Comparing Timestamps Without Timezone

**Problem**: Mixing local and UTC timestamps causes errors.

**Solution**: Always use UTC.

```python
# CORRECT
from datetime import datetime, timezone
now = datetime.now(timezone.utc)

# WRONG
now = datetime.now()  # Local timezone
```

### 3. Not Filtering Pool-Specific Parameter Changes

**Problem**: Tracking weight changes for regular weighted pools (they're immutable).

**Solution**: Use pool type filtering (Phase 7).

```python
# CORRECT - Phase 7 implementation
if event_type == "WeightsGraduallyChanged":
    if not _is_lbp_pool(pool_type, pool_name):
        return None  # Skip

# WRONG - Phase 4 implementation
if event_type == "WeightsGraduallyChanged":
    return ParameterChange(...)  # Tracks all weight changes
```

### 4. Assuming Tags Field Always Exists

**Problem**: V2 pools don't have tags field.

**Solution**: Check before using (Phase 8).

```python
# CORRECT
tags = pool_data.get("tags", [])
if tags and isinstance(tags, list):
    # Use tags

# WRONG
if "BOOSTED" in pool_data["tags"]:  # Crashes if no tags
```

### 5. Not Normalizing Pool Addresses

**Problem**: Case-sensitive comparisons fail.

**Solution**: Always lowercase.

```python
# CORRECT
pool_address = pool_address.lower()

# WRONG
if pool_address == "0x3DE27EFA...":  # Mixed case fails
```

---

## Testing Guidelines

### Test Structure

```bash
tests/
├── test_boosted_pool_analyzer.py      # 33 tests (Phase 1 + 8)
├── test_pool_history_analyzer.py      # 29 tests (Phase 4 + 7)
├── test_data_exporter.py              # 15 tests (Phase 2 + 6)
├── test_lp_return_calculator.py       # 18 tests (Phase 3)
├── test_full_integration.py           # 8 tests (Phase 5)
└── test_anchor_token_info.py          # 11 tests
```

### Running Tests

```bash
# All tests
pytest -v

# Specific module
pytest tests/test_boosted_pool_analyzer.py -v

# Specific test
pytest tests/test_boosted_pool_analyzer.py::test_is_pool_boosted_by_tags -v

# With coverage
pytest --cov=services --cov-report=html
```

### Writing New Tests

**Required Tests**:
1. Happy path (normal operation)
2. Edge cases (empty data, missing fields)
3. Error handling (API failures, invalid input)
4. Integration tests (multi-service workflows)

**Example**:
```python
@pytest.mark.asyncio
async def test_parameter_change_detection():
    """Test parameter change detection with realistic data."""
    analyzer = PoolHistoryAnalyzer()
    
    # Test LBP weight change (should be tracked)
    changes = await analyzer.detect_changes_in_period(
        pool_address="0xlbp_pool_address",
        days=30
    )
    assert any(c.change_type == "weights" for c in changes)
    
    # Test regular weighted pool (should skip weight changes)
    changes = await analyzer.detect_changes_in_period(
        pool_address="0xweighted_pool_address",
        days=30
    )
    assert not any(c.change_type == "weights" for c in changes)
```

---

## Future Considerations

### Surge Parameter Direct Queries

**Current Limitation**: Surge events may not be in subgraph.

**Future Enhancement**: Query hook contracts directly via Web3.

```python
# TODO: Implement Web3 integration
async def _get_surge_params_from_hook(self, hook_address: str):
    """Query surge parameters directly from hook contract."""
    from web3 import Web3
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    # Call getSurgeThreshold() function
    surge_threshold = w3.eth.call({
        "to": hook_address,
        "data": "0x..."  # Function selector
    })
    
    # Call getMaxSurgeFee() function
    max_surge_fee = w3.eth.call({
        "to": hook_address,
        "data": "0x..."  # Function selector
    })
    
    return surge_threshold, max_surge_fee
```

**Required Changes**:
1. Add Web3 to `requirements.txt`
2. Add RPC endpoint to `.env` configuration
3. Implement hook contract ABIs
4. Add hook address detection to `_is_surge_pool()`
5. Update `detect_changes_in_period()` to query hooks

### Additional Boosted Pool Types

**Current Support**: AAVE, EULER, YEARN, GEARBOX

**Future Protocols**:
- Morpho boosted pools
- Compound V3 boosted pools
- Custom protocol integrations

**To Add New Protocol**:
1. Add tag pattern to `get_boosted_pool_type()` in `boosted_pool_analyzer.py`
2. Add wrapped token mappings to `WRAPPED_TO_UNDERLYING` dict
3. Add test cases
4. Update documentation

### Hook Field in GraphQL Query

**Current Status**: Hook field not fetched from API.

**Future Enhancement**: Add hook field to query.

```graphql
{
  id
  address
  type
  tags
  hook {              # ADD THIS
    address
    type
  }
}
```

**Benefits**:
- Better surge pool detection
- Direct hook contract queries
- Hook-specific parameter tracking

---

## Environment Variables Reference

```env
# Balancer APIs
BALANCER_V3_API=https://api-v3.balancer.fi/
BALANCER_V2_SUBGRAPH=https://api.studio.thegraph.com/query/24617/balancer-v2
DEFAULT_CHAIN=MAINNET              # MAINNET, ARBITRUM, POLYGON, etc.
BLOCKCHAIN_NAME=ethereum           # ethereum, arbitrum, polygon, etc.

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Dune Analytics
DUNE_API_KEY=your_dune_api_key
DUNE_ANCHOR_VOLUME_QUERY_ID=6664013

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/pool_report
```

---

## Quick Reference Commands

```bash
# Start server
uvicorn main:app --reload

# Run tests
pytest -v

# Run specific phase tests
pytest tests/test_pool_history_analyzer.py -v  # Phase 7
pytest tests/test_boosted_pool_analyzer.py -v  # Phase 8

# Check exports
ls -lh exports/

# Clean old exports
python -c "from services.data_exporter import DataExporter; DataExporter().cleanup_old_exports()"

# Interactive anchor token test
echo -e "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48\nethereum" | python tests/interactive_anchor_test.py
```

---

## Getting Help

1. **Documentation**: Check `docs/new_features.md` for feature details
2. **Phase Instructions**: See `AI_Agent_files/phase_instructions/` for implementation guides
3. **Test Files**: Test files contain usage examples
4. **API Docs**: http://localhost:8000/docs (when server running)

---

**Document Version**: 1.0.0  
**Last Updated**: February 12, 2026  
**Maintained By**: Balancer Pool Reporter Team
