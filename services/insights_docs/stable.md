# Stable Pools (Composable/Stable/MetaStable) - Deep Context

## Pool Type Overview
Stable Pools are specialized automated market makers (AMMs) designed for assets that maintain a tight peg relationship. Unlike constant product pools (x*y=k), they use the StableSwap invariant which provides significantly better capital efficiency for low-volatility pairs.

**Primary Use Cases:**
- Stablecoin swaps (USDC/USDT/DAI)
- Liquid staking derivatives (wstETH/wETH, rETH/ETH)
- Wrapped/synthetic asset pairs (WBTC/renBTC)
- Same-peg assets across different networks

## Technical Characteristics

### Amplification Parameter (A)
- Controls curve behavior between constant sum (A=∞) and constant product (A=0)
- Higher A = tighter concentration around 1:1 ratio = more capital efficiency
- Typical ranges:
  - Stablecoins: A = 50-200
  - LST pairs: A = 20-100
  - Volatile pegged assets: A = 5-50
- **Analysis point:** If A is too high for actual volatility, the pool risks impermanent loss

### Fee Structure
- Swap fees typically 0.01% - 0.04% (vs 0.3%+ for volatile pairs)
- Low fees justified by:
  - Minimal IL risk for LPs
  - High competition (many stable pool options)
  - Volume-based revenue model
- **Red flag:** Fees >0.1% usually indicate poor pool design or lack of competition

## Key Metrics & Interpretation Framework

### 1. Total Value Locked (TVL)
**What it tells you:**
- Absolute TVL indicates market share and swap capacity
- TVL concentration: 80%+ in one asset suggests imbalanced pool
- Ideal: 45-55% balance between assets

**Analysis patterns:**
- **Growing TVL + Growing Volume** = Healthy pool attracting both LPs and traders
- **Growing TVL + Flat Volume** = Yield farming/incentive-driven (may be temporary)
- **Shrinking TVL + Stable Volume** = LPs exiting despite usage (investigate yields)
- **Shrinking TVL + Shrinking Volume** = Pool losing market share (competitor check)

**Comparative benchmarks:**
- Dominant stable pools: $50M+ TVL
- Competitive pools: $5M-50M TVL
- Niche/new pools: <$5M TVL

### 2. Volume Metrics
**Daily/Weekly Volume:**
- Measures actual utility and trading activity
- High volume = strong product-market fit

**Volume/TVL Ratio (Turnover):**
- **<0.05 (5%)**: Underutilized pool, excess liquidity
- **0.05-0.20**: Healthy range for stable pools
- **0.20-0.50**: High utilization, efficient capital deployment
- **>0.50**: Potentially insufficient liquidity, check slippage

**Volume trends:**
- Spikes: Check for depegging events, arbitrage opportunities, protocol migrations
- Steady growth: Indicates organic adoption
- Declining volume: Market share loss or reduced trading activity

### 3. Fee Revenue & APR
**Fee Revenue = Daily Volume × Swap Fee**

**LP APR Calculation:**
- Base Fee APR = (Annual Fee Revenue / TVL) × 100
- Total APR = Fee APR + Token Incentives APR

**Interpretation:**
- **Fee APR < 2%**: Pool may struggle to retain liquidity without incentives
- **Fee APR 2-8%**: Competitive for stable pools
- **Fee APR > 8%**: Either very efficient or depegging risk (investigate)

**Sustainability check:**
- What % of APR comes from fees vs. incentives?
- >50% from incentives = high risk when incentives end

### 4. Liquidity Depth & Slippage
**Price Impact Analysis:**
- For $100K swap: <0.05% impact = excellent
- For $100K swap: 0.05-0.15% = good
- For $100K swap: >0.15% = insufficient depth

**Capacity indicators:**
- Maximum efficient swap size ≈ 1-2% of TVL for stable pools
- Larger swaps should route through aggregators

## Pool Health Signals

### Positive Signals
✓ Consistent daily volume (low volatility in usage)
✓ Balanced asset ratios (within 40-60% range)
✓ Volume/TVL ratio between 0.10-0.30
✓ Fee APR covering at least 30% of competitive yields
✓ Growing number of unique traders
✓ Stable or growing LP count

### Warning Signals
⚠ Asset ratio drifting (one asset >60%)
⚠ Sudden volume spikes (check for depeg)
⚠ Volume/TVL <0.05 for >2 weeks
⚠ Fee APR <1% without incentives
⚠ Decreasing unique traders
⚠ LP concentration (top 3 LPs >70% of pool)

### Critical Risks
🚨 Asset depeg >2% from expected ratio
🚨 Rapid TVL exodus (>20% in 24h)
🚨 Volume/TVL ratio <0.01
🚨 Single LP controlling >50% of pool
🚨 Smart contract vulnerabilities or paused state

## Competitive Analysis Framework

### Market Position Questions
1. What's the pool's market share vs. competitors (same pair)?
2. Is TVL growth outpacing or lagging category average?
3. How do swap fees compare to equivalent pools?
4. What's the historical fee APR vs. competitor pools?

### Yield Competitiveness
- Compare against: Aave/Compound lending rates for same assets
- Typical spread: Stable pool APR should be 1-3% above lending rates
- If below lending rates: LPs should exit to lending protocols

## Advanced Analysis Techniques

### Peg Deviation Monitoring
- Track asset ratio changes over 7/30/90 days
- Persistent deviation indicates:
  - Asymmetric trading flow (investigate why)
  - Potential depeg risk building
  - Arbitrage opportunities being missed

### Volume Pattern Analysis
**Weekly cycles:**
- DeFi volume often lower on weekends
- Anomalies suggest automated trading/bots

**Event-driven volume:**
- Correlate spikes with: protocol launches, depegs, yield changes, token incentives
- Sustainable volume should be event-independent

### LP Profitability Estimation
```
LP Profit = Fee Revenue - Opportunity Cost - IL
- Opportunity Cost: Lending APR on same assets
- IL: Minimal for stable pools unless depeg occurs
```

## Data Quality & Reliability Checks
- Cross-reference TVL with on-chain data (not just reported)
- Verify volume isn't wash trading (check unique trader count)
- Confirm fee collection (some protocols take performance fees)
- Check if pool is actually being used by aggregators (1inch, Cowswap, etc.)

## Contextual Factors to Consider

### Protocol-Level
- Does the protocol offer incentives (BAL/veBAL boosting on Balancer)?
- Are there gauge votes directing liquidity?
- Protocol treasury health and sustainability

### Market-Level
- Overall stablecoin market trends (USDC dominance, regulatory changes)
- LST market growth (ETH staking adoption)
- Competitive landscape changes (new DEXes, improved pricing)

### Chain-Level
- Gas costs impact profitability (higher on Ethereum mainnet)
- Bridge liquidity affects cross-chain stable pools
- Chain-specific stablecoin preferences

## Output Recommendations for Analysis

When analyzing a stable pool, your model should provide:

1. **Health Score (0-100)** based on weighted metrics
2. **Primary Use Case Confirmation** (what traders actually use it for)
3. **Efficiency Rating** (capital utilization vs. optimal)
4. **Risk Assessment** (depeg risk, concentration risk, smart contract risk)
5. **Competitive Positioning** (vs. similar pools)
6. **LP Recommendation** (enter/hold/exit with reasoning)
7. **Optimization Suggestions** (fee adjustments, A parameter, incentives)
8. **Trend Direction** (growing/stable/declining with evidence)

## Example Analysis Template

**Pool:** [Name]
**TVL:** $X | **Volume (24h):** $Y | **Fee:** Z%
**Health Score:** [0-100]

**Findings:**
- Utilization: [Volume/TVL ratio and interpretation]
- Balance: [Asset ratio assessment]
- Yield: [Fee APR vs. alternatives]
- Trend: [7/30 day trajectory]

**Risks:** [Key concerns]
**Opportunities:** [Potential improvements]
**Recommendation:** [Actionable insight]