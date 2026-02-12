# New Features Guide

This document provides detailed information about the new features added in Phases 1-8 of the Balancer Pool Reporter enhancement project.

## Table of Contents

1. [Boosted Pool Support (Phase 1 + Phase 8)](#boosted-pool-support-phase-1--phase-8)
2. [Data Export (Phase 2 + Phase 6)](#data-export-phase-2--phase-6)
3. [Hold vs Pool Analysis (Phase 3)](#hold-vs-pool-analysis-phase-3)
4. [Parameter Change Detection (Phase 4 + Phase 7)](#parameter-change-detection-phase-4--phase-7)

---

## Boosted Pool Support (Phase 1 + Phase 8)

### What It Does

Automatically detects Balancer boosted pools (pools containing ERC-4626 wrapped tokens) and extracts the underlying tokens for accurate competitor discovery and analysis.

### How It Works

**Phase 1 Implementation:**
1. **Heuristic Detection**: Checks if a pool is boosted using multiple criteria:
   - Pool type (e.g., "ComposableStable", "Boosted", "AaveLinear")
   - Pool name (e.g., starts with "bb-" or contains "boosted")
   - Token symbols (e.g., contains "a" prefix for Aave tokens)

**Phase 8 Enhancement - API Tags (Priority Detection):**
2. **Tags-Based Detection** (NEW): Uses Balancer API `tags` field for accurate identification:
   - `BOOSTED_AAVE` → Aave boosted pool
   - `BOOSTED_EULER` → Euler boosted pool
   - `BOOSTED_YEARN` → Yearn boosted pool
   - `BOOSTED_GEARBOX` → Gearbox boosted pool
   - `BOOSTED` → Generic boosted pool
   - **Fallback**: If tags not available, uses Phase 1 heuristics

**Detection Priority:**
1. Check API tags field (most reliable)
2. Fallback to heuristic detection (pool type, name, token symbols)

3. **Underlying Token Extraction**: When a pool is 100% boosted, extracts underlying tokens:
   - `aUSDC` → `USDC`
   - `aDAI` → `DAI`
   - `wstETH` → `ETH`
   - And more (see full mapping below)

4. **Integration**: Used automatically in the metrics pipeline when finding competitor pools
5. **Excel Export**: Multi-pool exports include "Boosted" column showing pool type (AAVE, EULER, etc.)

### Supported Wrapped Tokens

| Wrapped Token | Underlying Token | Protocol |
|---------------|------------------|----------|
| aUSDC, aDAI, aUSDT | USDC, DAI, USDT | Aave |
| cUSDC, cDAI | USDC, DAI | Compound |
| bb-a-USD | USD stablecoins | Balancer Boosted |
| wstETH, stETH | ETH | Lido |
| rETH | ETH | Rocket Pool |
| cbETH | ETH | Coinbase |

### API Usage

```python
from services.boosted_pool_analyzer import (
    is_pool_boosted,
    is_100_percent_boosted,
    get_underlying_tokens,
    get_boosted_pool_type  # NEW in Phase 8
)

# Check if pool is boosted
pool_data = {"pool_type": "ComposableStable", "tokens": [...], "tags": ["BOOSTED_AAVE"]}
if is_pool_boosted(pool_data):
    print("This is a boosted pool!")
    
    # Get specific boosted type (Phase 8)
    boosted_type = get_boosted_pool_type(pool_data)
    print(f"Boosted Type: {boosted_type}")  # Output: "AAVE"

# Check if 100% boosted
if is_100_percent_boosted(pool_data):
    # Extract underlying tokens
    underlying = get_underlying_tokens(pool_data["tokens"])
    print(f"Underlying tokens: {underlying}")
```

### Example

**Input Pool**: bb-a-USD (contains aUSDC, aDAI, aUSDT)

**Detection Result**:
- ✅ Boosted: Yes
- ✅ 100% Boosted: Yes
- ✅ Underlying Tokens: USDC, DAI, USDT

**Competitor Search**: Uses USDC, DAI, USDT to find similar pools on other DEXes

---

## Data Export (Phase 2 + Phase 6)

### What It Does

Exports comprehensive pool metrics to Excel or CSV format for offline analysis, reporting, and custom visualizations. **Phase 6 adds full multi-pool export support** with advanced Excel layouts.

### Formats Available

#### 1. Excel (.xlsx)

**Single-Pool Excel (3 tabs):**

**Sheet 1: all_metrics**
- Every metric for every pool (input + competitors)
- Organized by pool and metric group
- Includes metric units (USD, %, Count, etc.)

**Sheet 2: summary**
- High-level overview of all pools
- Key metrics only (TVL, volume, APR, etc.)
- Easy comparison across pools

**Sheet 3: anchor_tokens** (if anchor token analysis enabled)
- Lending market data
- Trading volume data
- Best lending opportunities

**Multi-Pool Excel (4 tabs) - Phase 6:**

**Sheet 1: Pool Comparison** (NEW)
- Side-by-side comparison of all pools
- Key metrics: TVL, volume, fees, APR
- **Boosted column** (Phase 8): Shows boosted pool type (AAVE, EULER, etc.)
- Pool type, URL, and performance indicators

**Sheet 2: Rankings** (NEW)
- Top 3 pools by volume
- Top 3 pools by TVL growth
- Custom ranking metrics (if specified)

**Sheet 3: Summary** (NEW)
- Total TVL across all pools
- Total fees collected
- Weighted average APR
- Number of boosted pools (Phase 8)
- Anchor token best market summary

**Sheet 4: Anchor Token**
- Same as single-pool anchor token data

#### 2. CSV (.csv)

Single file with flattened data:
- All metrics from all pools
- One row per metric per pool
- Easy to import into pandas, Excel, or BI tools

### Export Structure

| Column | Description |
|--------|-------------|
| pool_name | Pool name |
| pool_address | Pool address |
| pool_type | "Input Pool" or "Competitor" |
| dex | DEX name (Balancer, UniSwap, etc.) |
| metric_group | Group name (8 groups total) |
| metric_name | Specific metric |
| metric_value | Numeric value |
| metric_unit | Unit (USD, %, Count, etc.) |

### API Usage

#### Via API Endpoint

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
    "anchor_token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "export_format": "both",
    "recipient_email": "user@example.com"
  }'
```

**Response**:
```json
{
  "message": "Report generated successfully",
  "export_files": {
    "excel": "exports/pool_report_20240211_123456.xlsx",
    "csv": "exports/pool_report_20240211_123456.csv"
  }
}
```

#### Direct Python Usage

```python
from services.data_exporter import DataExporter

exporter = DataExporter()

# Export to Excel
excel_path = exporter.export_to_excel(results, filename="my_report.xlsx")

# Export to CSV
csv_path = exporter.export_to_csv(results, filename="my_report.csv")

# Auto-cleanup old exports (keeps last 10)
exporter.cleanup_old_exports(max_files=10)
```

### Features

- ✅ Automatic file naming with timestamps
- ✅ Organized by metric groups
- ✅ Clean column headers
- ✅ Proper data types (numeric, string, date)
- ✅ Auto-cleanup of old exports
- ✅ Handles missing data gracefully
- ✅ **Multi-pool support** (Phase 6)
- ✅ **Boosted column in exports** (Phase 8)
- ✅ **Smart file naming** (single pool: `PoolReport_0x3de27efa_USDC_timestamp.xlsx`, multi-pool: `PoolReport_3pools_USDC_timestamp.xlsx`)

---

## Hold vs Pool Analysis (Phase 3)

### What It Does

Compares the returns of providing liquidity in a pool versus simply holding the tokens in a wallet. Helps LPs understand if pool participation is profitable.

### Calculation Method

#### Hold Strategy Return

```
Hold Return = ((Current Token Value) - (Initial Token Value)) / (Initial Token Value) × 100%
```

Where:
- Initial Token Value = Value of tokens N days ago
- Current Token Value = Value of same tokens today
- Uses historical prices from CoinGecko

#### Pool Strategy Return

```
Pool Return = Hold Return + Fees Earned + Incentives - Impermanent Loss
```

Components:
1. **Fees Earned**: Trading fees from pool swaps
2. **Incentives**: BAL rewards or partner tokens
3. **Impermanent Loss**: Loss from price divergence between tokens

### Metrics Calculated

**Hold Strategy**:
- Starting value (USD)
- Ending value (USD)
- Return (%)

**Pool Strategy**:
- Starting pool value (USD)
- Fees earned (USD)
- Incentives earned (USD)
- Impermanent loss (USD)
- Total return (%)

**Comparison**:
- Winner: "hold" or "pool"
- Difference (percentage points)
- Recommendation (human-readable)

### API Usage

#### Via Python

```python
from services.lp_return_calculator import LPReturnCalculator

calc = LPReturnCalculator()

# Calculate for 30-day period
result = await calc.calculate_hold_vs_pool(
    pool_address="0x3de27efa2f1aa663ae5d458857e731c129069f29",
    days=30
)

print(f"Hold Return: {result['hold_strategy']['return_pct']:.2f}%")
print(f"Pool Return: {result['pool_strategy']['return_pct']:.2f}%")
print(f"Winner: {result['comparison']['winner']}")
print(f"Recommendation: {result['comparison']['recommendation']}")
```

### Interpretation Guide

| Scenario | Winner | Meaning |
|----------|--------|---------|
| Pool return > Hold return | pool | LP fees/incentives exceeded IL |
| Hold return > Pool return | hold | IL exceeded fees/incentives |
| Difference < 1% | tie | Both strategies roughly equal |

### Example Output

```
Hold Strategy:
  Start Value: $10,000.00
  End Value: $10,500.00
  Return: +5.00%

Pool Strategy:
  Start Value: $10,000.00
  Fees Earned: $120.00
  Incentives: $80.00
  Impermanent Loss: -$50.00
  Total Return: +6.50%

Winner: POOL
Difference: +1.50 percentage points
Recommendation: Providing liquidity was more profitable than holding
```

### Limitations

- Requires historical price data (30+ days)
- Impermanent loss calculation assumes proportional withdrawals
- Does not account for gas fees
- Incentives may be estimates if not directly available

---

## Parameter Change Detection (Phase 4 + Phase 7)

### What It Does

Automatically detects when pool parameters change (swap fees, weights, gauge additions) and analyzes the impact on pool performance. **Phase 7 adds refined filtering** to track only relevant parameter changes based on pool type.

### Tracked Changes

| Change Type | Description | Detection Method | Phase |
|-------------|-------------|------------------|-------|
| Swap Fee Change | Fee % adjustments | SwapFeePercentageChanged event | Phase 4 |
| Weight Change (LBP only) | Token weight rebalancing | WeightsGraduallyChanged event | **Phase 7** |
| Amp Factor (Stable pools) | Amplification parameter updates | AmpUpdateStarted/Stopped events | **Phase 7** |
| Surge Threshold (Stable Surge) | Surge activation threshold | SurgeThresholdChanged event | **Phase 7** |
| Max Surge Fee (Stable Surge) | Maximum surge fee cap | SurgeFeeChanged event | **Phase 7** |

**Phase 7 Refinements:**
- **Weight Changes**: Now filtered to **LBP pools only** (Liquidity Bootstrapping Pools). Regular weighted pools have immutable weights and are correctly ignored.
- **Amp Factor**: Tracks amplification parameter changes in **stable pools only** (e.g., StablePhantom, ComposableStable).
- **Surge Parameters**: Support for stable surge pools (stored in hook contracts). Events may not be available in subgraph yet - implementation is future-proof.

### Impact Analysis

For each change, the analyzer:

1. **Identifies the change**: Type, timestamp, old/new values
2. **Measures impact**: Compares metrics 7 days before vs 7 days after
3. **Generates summary**: Human-readable impact description

#### Metrics Compared

- Volume change (%)
- TVL change (%)
- APR change (%)

### API Usage

#### Via Python

```python
from services.pool_history_analyzer import PoolHistoryAnalyzer

analyzer = PoolHistoryAnalyzer()

# Detect changes in last 30 days
changes = await analyzer.detect_changes_in_period(
    pool_address="0x3de27efa2f1aa663ae5d458857e731c129069f29",
    days=30
)

for change in changes:
    print(f"Type: {change.change_type}")
    print(f"Date: {datetime.fromtimestamp(change.timestamp)}")
    print(f"Impact: {change.impact_summary}")
```

#### Analyze Specific Change

```python
# Analyze impact of a specific change
impact = await analyzer.analyze_impact_of_change(
    pool_address="0x3de27efa2f1aa663ae5d458857e731c129069f29",
    change_timestamp=1234567890,
    change_type="swap_fee_change"
)

print(f"Volume change: {impact['metrics_change']['volume_change_pct']:.2f}%")
print(f"TVL change: {impact['metrics_change']['tvl_change_pct']:.2f}%")
```

### Example Output

```
Parameter Change Detected:
  Type: Swap Fee Change
  Date: 2024-01-15 10:30:00 UTC
  Old Fee: 0.30%
  New Fee: 0.25%

Impact Analysis (7 days before vs 7 days after):
  Volume: +12.5% increase
  TVL: +3.2% increase
  APR: -1.8% decrease

Summary: Fee reduction led to increased trading activity but slightly 
         lower returns for LPs. Overall positive impact on liquidity.
```

### Data Structure

```python
@dataclass
class ParameterChange:
    timestamp: int           # Unix timestamp
    change_type: str         # "swap_fee_change", "weight_change", etc.
    block_number: int        # Block number
    old_value: str | None    # Previous value (if available)
    new_value: str | None    # New value (if available)
    impact_summary: str | None  # Human-readable impact
```

### Limitations

- Requires at least 14 days of data around the change (7 before + 7 after)
- Cannot separate impact of parameter change from external market factors
- Some events may not have detailed before/after values
- Gauge events are detected but may have limited impact data

---

## Integration Notes

All four features are designed to work together seamlessly:

1. **Boosted Pool Support** ensures accurate competitor discovery
2. **Data Export** provides all metrics (including hold vs pool) in exportable format
3. **Hold vs Pool Analysis** adds profitability insights to reports
4. **Parameter Change Detection** explains historical performance changes

### Automatic Integration

When you call the `/report` endpoint, all features are automatically used:

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
    "anchor_token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "export_format": "both",
    "recipient_email": "user@example.com"
  }'
```

**What Happens**:
1. ✅ Detects if pool is boosted via API tags (Phase 8) or heuristics (Phase 1)
2. ✅ Identifies specific boosted type (AAVE, EULER, etc.) - Phase 8
3. ✅ Finds competitors using underlying tokens if boosted
4. ✅ Calculates hold vs pool (Phase 3)
5. ✅ Detects parameter changes with refined filtering (Phase 7):
   - Weight changes only for LBP pools
   - Amp factor changes for stable pools
   - Surge parameters for stable surge pools
6. ✅ Exports everything to Excel/CSV with multi-pool support (Phase 2 + 6)
7. ✅ Includes "Boosted" column in multi-pool exports (Phase 8)
8. ✅ Sends Telegram report with all insights

---

## Testing

Each phase has comprehensive test coverage:

```bash
# Test individual phases
pytest tests/test_boosted_pool_analyzer.py -v    # 33 tests (Phase 1 + 8)
pytest tests/test_data_exporter.py -v            # 15 tests (Phase 2 + 6)
pytest tests/test_lp_return_calculator.py -v     # 18 tests (Phase 3)
pytest tests/test_pool_history_analyzer.py -v    # 29 tests (Phase 4 + 7)

# Test full integration
pytest tests/test_full_integration.py -v         # 8 tests (Phase 5)
```

**Total Test Coverage: 114+ tests**

---

## Performance Considerations

- **Boosted Pool Detection**: < 1ms (local logic only)
- **Data Export**: 1-3 seconds (depends on data size)
- **Hold vs Pool**: 5-15 seconds (CoinGecko + Balancer APIs)
- **Parameter Detection**: 10-30 seconds (event queries + impact analysis)

**Total Pipeline**: Typically completes within 30-60 seconds for a single pool with all features enabled.

---

## Known Limitations

1. **Hold vs Pool**:
   - Requires 30+ days of historical price data
   - May not be available for very new tokens
   - Incentives are estimates if not directly available

2. **Parameter Detection (Phase 7 Updates)**:
   - Cannot separate parameter impact from market conditions
   - Requires sufficient historical data (14+ days around change)
   - **Surge events may not be available in Balancer subgraph yet** (implementation is future-proof)
   - Surge parameters stored in hook contracts (not pool contracts) - requires Web3 integration for direct queries

3. **Boosted Pools (Phase 8 Updates)**:
   - Tags field may not be available for all pools (V2 pools may lack tags)
   - Heuristic fallback works but is less reliable than tags
   - Only supports known wrapped token types
   - May not detect custom/experimental wrapped tokens
   - Manual mapping required for new protocols

4. **Data Export**:
   - Excel files can be large for many competitors (10+ MB)
   - CSV format loses metric grouping structure
   - Old exports need periodic cleanup (auto-cleanup after 24 hours)

---

## Future Enhancements

Potential improvements for future phases:

- [ ] Real-time parameter change notifications
- [ ] Advanced impermanent loss visualization
- [ ] Support for more wrapped token types
- [ ] Historical hold vs pool tracking (multiple periods)
- [ ] Export to Google Sheets
- [ ] PDF report generation
- [ ] Automated parameter optimization suggestions

---

## Support

For questions or issues with these features:
1. Check the test files for usage examples
2. Review the phase instruction documents in `AI_Agent_files/phase_instructions/`
3. Open an issue on the repository

---

**Last Updated**: February 12, 2026
**Documentation Version**: 2.0.0 (includes Phases 1-8)
