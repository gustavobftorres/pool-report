# Weighted Pools - Deep Context

## Pool Type Overview
Weighted Pools are Balancer's flagship AMM innovation, extending the constant product formula (x*y=k) to support multiple tokens with arbitrary weights. Unlike traditional 50/50 pools, they enable asymmetric exposure while maintaining continuous liquidity.

**Core Innovation:**
The weighted math invariant: `(balance_1)^(weight_1) * (balance_2)^(weight_2) * ... = k`

**Primary Use Cases:**
- Governance token liquidity with reduced IL (80/20 pools)
- Index fund-like exposure (33/33/33 or 25/25/25/25)
- Directional LP positions (70/30 for bullish exposure)
- Protocol-owned liquidity with asymmetric holdings
- Multi-asset treasury management

## Weight Configuration Fundamentals

### Common Weight Patterns

**80/20 Pools (Most Popular)**
- **Use case:** Protocol token + stablecoin/ETH
- **LP perspective:** 80% exposure to volatile asset, 20% price stability
- **Benefit:** ~5x less impermanent loss than 50/50 for same price movement
- **Example:** 80% AURA / 20% ETH

**60/40 Pools**
- **Use case:** Moderate asymmetric exposure
- **LP perspective:** Balanced between directional bet and liquidity provision
- **Benefit:** ~2x less IL than 50/50
- **Example:** 60% GNO / 40% WETH

**50/50 Pools (Traditional)**
- **Use case:** Equal exposure to both assets
- **LP perspective:** Neutral position, maximum rebalancing
- **Benefit:** Highest trading fees (more rebalancing)
- **Example:** 50% WETH / 50% USDC

**Multi-token Pools (3-8 tokens)**
- **Use case:** Index funds, diversified exposure
- **LP perspective:** Basket investment with auto-rebalancing
- **Common patterns:** 33/33/33, 25/25/25/25, or custom allocations
- **Example:** 40% WETH / 30% WBTC / 30% USDC

### Weight Impact on Pool Behavior

**Mathematical relationship:**
- Higher weight = less price impact from that token's trades
- Lower weight = higher price impact, more fees from rebalancing
- Weights determine how pool ratio changes with price

**Impermanent Loss by Weight:**
For a 2x price increase in token A:
- **50/50 pool:** ~5.7% IL
- **60/40 pool:** ~3.8% IL (A is 60%)
- **70/30 pool:** ~2.3% IL (A is 70%)
- **80/20 pool:** ~1.2% IL (A is 80%)
- **90/10 pool:** ~0.4% IL (A is 90%)

**Critical insight:** Higher weight in appreciating asset = lower IL but also lower fee generation

## Key Metrics & Interpretation Framework

### 1. Total Value Locked (TVL)

**Weight-Adjusted TVL Analysis:**
```
For 80/20 AURA/ETH pool with $10M TVL:
- AURA TVL: $8M
- ETH TVL: $2M
```

**What to monitor:**
- **Absolute TVL:** Market depth and swap capacity
- **TVL per token:** Actual liquidity available for each asset
- **Weight deviation:** Actual ratio vs. target ratio

**Deviation formula:**
```
Deviation = |Actual Weight - Target Weight| / Target Weight
Healthy: <5%
Warning: 5-15%
Critical: >15%
```

**Analysis patterns:**

**Scenario 1: Growing TVL + Weights in balance**
- Interpretation: New LPs entering, healthy demand
- Action: Monitor for sustained growth

**Scenario 2: Growing TVL + Weight imbalance (e.g., 85/15 in 80/20 pool)**
- Interpretation: One-sided price movement, LPs not rebalancing
- Risk: Pool becoming less useful for opposite-direction trades
- Action: Check if arb opportunities exist

**Scenario 3: Shrinking TVL + Weights balanced**
- Interpretation: Coordinated LP exit (incentives ended, better yields elsewhere)
- Action: Investigate competitive landscape

**Scenario 4: Shrinking TVL + Weight imbalance**
- Interpretation: Price dumping + LP panic
- Risk: Death spiral potential
- Action: Critical risk assessment needed

### 2. Volume Metrics

**Volume Distribution by Token:**
Not all volume is equal in weighted pools. Track:
- % of volume in token A → B
- % of volume in token B → A

**Interpretation examples:**

**80/20 TOKEN/ETH pool:**
- **75% volume is ETH→TOKEN, 25% is TOKEN→ETH**
  - Signal: Strong buying pressure, bullish
  - LP impact: Pool accumulating ETH, selling TOKEN
  - Risk: Pool weight could drift to 85/15 or worse

- **25% volume is ETH→TOKEN, 75% is TOKEN→ETH**
  - Signal: Selling pressure, bearish
  - LP impact: Pool accumulating TOKEN, selling ETH
  - Risk: Pool weight could drift to 75/25, LPs exit

- **50/50 volume split**
  - Signal: Balanced two-way flow, healthy trading
  - LP impact: Minimal weight drift
  - Ideal: This is optimal for LP returns

**Volume/TVL Ratio (Turnover):**

For weighted pools:
- **<0.03**: Very low utilization, likely sitting idle
- **0.03-0.10**: Below average, check competitiveness
- **0.10-0.30**: Healthy range for weighted pools
- **0.30-0.60**: High utilization, efficient capital
- **>0.60**: Very high utilization, may need more depth

**Benchmark by pool type:**
- Protocol token 80/20 pools: typically 0.05-0.15
- Major asset 50/50 pools: typically 0.15-0.40
- Index pools (4+ tokens): typically 0.03-0.10

### 3. Fee Structure & Revenue

**Swap Fee Dynamics:**

**By pool type:**
- **80/20 protocol token pools:** 0.3% - 1.0%
  - Higher fees justified by: lower competition, directional LPs less fee-sensitive
  - Lower fees when: high competition, volume-seeking strategy

- **50/50 major pairs:** 0.1% - 0.5%
  - Higher fees: exotic pairs, lower volume tolerance
  - Lower fees: high competition (WETH/USDC), volume-seeking

- **Multi-token index pools:** 0.2% - 0.5%
  - Moderate fees reflecting: convenience premium, auto-rebalancing value

**Fee Revenue Analysis:**
```
Daily Fee Revenue = Daily Volume × Swap Fee
Annual Run Rate = Daily Fee Revenue × 365
Fee APR = (Annual Run Rate / TVL) × 100
```

**Interpretation framework:**

**Fee APR ranges by pool type:**

**80/20 Governance Token Pools:**
- **<3%**: Underperforming, LPs likely subsidized by incentives
- **3-8%**: Competitive, depends on token volatility
- **8-15%**: Good performance, attractive without incentives
- **>15%**: Excellent, but verify volume sustainability

**50/50 Major Asset Pools:**
- **<5%**: Poor performance vs. alternatives
- **5-15%**: Competitive range
- **15-30%**: Strong performance
- **>30%**: Exceptional, check for temporary factors

**Multi-token Index Pools:**
- **<2%**: Underutilized
- **2-6%**: Competitive for passive exposure
- **6-12%**: Strong performance
- **>12%**: Excellent, rare for index pools

### 4. Impermanent Loss Tracking

**Calculate Actual IL:**
```
IL% = (Value if held) - (Value in pool) / (Value if held) × 100
```

**For 80/20 pools, simplified estimation:**
If token A increases 2x relative to token B:
```
IL ≈ 1.2% for 80% weight in A
IL ≈ 5.7% for 50% weight in A
```

**IL vs. Fee Revenue Analysis:**

**Healthy scenarios:**
- IL = 3%, Fee Revenue = 8% → Net +5% ✓
- IL = 10%, Fee Revenue = 20% → Net +10% ✓

**Problematic scenarios:**
- IL = 15%, Fee Revenue = 5% → Net -10% ✗
- IL = 8%, Fee Revenue = 3% → Net -5% ✗

**Critical question:** Has cumulative fee revenue offset IL?
- Track over 30/90/180 day periods
- If consistently negative, LPs should exit

### 5. Liquidity Depth & Price Impact

**Effective Depth by Weight:**

For an 80/20 pool with $5M TVL:
- Major token (80%): $4M effective liquidity
- Minor token (20%): $1M effective liquidity

**Price impact expectations:**

**$10k swap:**
- Well-balanced pool: <0.1%
- Imbalanced pool: 0.1-0.3%
- Poor liquidity: >0.3%

**$100k swap:**
- Deep pool (>$10M TVL): 0.2-0.5%
- Medium pool ($1M-10M): 0.5-1.5%
- Shallow pool (<$1M): >2%

**Red flag:** If price impact for $50k swap >1%, pool is undersized for its trading pairs

## Pool Health Signals

### Positive Signals

✓ **Weight stability:** Actual weights within 3% of targets over 7 days
✓ **Bidirectional volume:** Both directions represent 30-70% of total volume
✓ **Consistent turnover:** Volume/TVL ratio stable week-over-week
✓ **Fee APR > IL:** Cumulative fees exceed impermanent loss over 90 days
✓ **Growing unique traders:** Indicates organic discovery and usage
✓ **LP count increasing:** New liquidity providers entering
✓ **Competitive fees:** APR in top 50% of similar pools
✓ **Low concentration:** Top 5 LPs <60% of total TVL

### Warning Signals

⚠ **Weight drift:** Actual ratio deviating 5-10% from target
⚠ **One-sided volume:** >80% of volume in one direction for 3+ days
⚠ **Declining turnover:** Volume/TVL dropping >30% week-over-week
⚠ **Fee APR declining:** Dropping below 50% of 30-day average
⚠ **LP exodus:** LP count decreasing >10% per week
⚠ **Incentive dependency:** >70% of APR from token incentives
⚠ **Increasing concentration:** Top 3 LPs now >70% of TVL
⚠ **Volatile fee APR:** Daily variance >50% (sign of unstable usage)

### Critical Risks

🚨 **Severe weight imbalance:** >15% deviation from target weights
🚨 **Volume collapse:** 7-day volume <20% of 30-day average
🚨 **Death spiral:** Declining TVL + declining volume simultaneously
🚨 **IL exceeds fees:** Net LP losses for 90+ consecutive days
🚨 **Single LP dominance:** One LP >50% of pool
🚨 **Smart contract issues:** Paused state, emergency mode, or known vulnerabilities
🚨 **Token crash:** One asset down >80% in 7 days
🚨 **Liquidity crisis:** Cannot support $10k swap with <2% impact

## Competitive Analysis Framework

### Market Position Assessment

**For protocol token pools (80/20 pattern):**

1. **Primary liquidity venue check:**
   - Is this the largest pool for the token?
   - What % of total token DEX liquidity?
   - Dominant (>60%), Competitive (30-60%), Marginal (<30%)

2. **Cross-DEX comparison:**
   - Balancer pool vs. Uniswap v2/v3 alternatives
   - Fee generation comparison
   - Capital efficiency comparison

3. **Incentive comparison:**
   - BAL/veBAL incentives on this pool
   - Competing pool incentives (UNI, CRV, etc.)
   - Net APR after all incentives

**For major asset pools (50/50 or other):**

1. **Liquidity ranking:**
   - Where does TVL rank vs. all ETH/USDC pools?
   - Is this competitive with concentrated liquidity (Uni v3)?

2. **Fee competitiveness:**
   - How do fees compare to Uniswap v3 equivalent ranges?
   - Is volume justified given fee level?

3. **Unique value proposition:**
   - Multi-hop routing benefits?
   - Part of larger pool ecosystem?
   - veBAL voting power benefits?

### Weight Optimization Analysis

**Is the current weight optimal?**

**For 80/20 pools, consider shift to:**
- **90/10:** If IL is still too high, volatility extreme
- **70/30:** If fees are too low, need more rebalancing
- **50/50:** If token has matured, less directional

**Evaluation criteria:**
```
Score = (Fee APR - IL%) × Volume × LP_satisfaction

Test different weights in simulation:
- Would 70/30 generate 30% more fees?
- Would 90/10 reduce IL enough to attract more LPs?
```

## Advanced Analysis Techniques

### 1. Weight Drift Velocity

**Track rate of weight change:**
```
Drift Velocity = (Weight_today - Weight_7days_ago) / 7
```

**Interpretation:**
- **+0.5% per day:** Strong buying, pool selling into demand
- **-0.5% per day:** Strong selling, pool buying the dump
- **±0.1% per day:** Normal fluctuation
- **±2% per day:** Extreme movement, investigate immediately

### 2. Directional Flow Analysis

**Calculate flow imbalance:**
```
Flow Imbalance = (Volume_A→B - Volume_B→A) / Total_Volume

-100% = All volume one direction
0% = Perfect balance
+100% = All volume opposite direction
```

**Interpretation by pool type:**

**80/20 Protocol Token Pool:**
- **-20% to +20%:** Healthy, balanced interest
- **+40%:** Strong accumulation phase
- **-40%:** Distribution/selling phase
- **±60%+:** Extreme one-sided flow, risk alert

### 3. LP Profitability Cohort Analysis

**Track LP entry/exit profitability:**
```
For LPs who entered 30 days ago:
Entry TVL Weight: X%/Y%
Current Weight: X'%/Y'%
Fees Earned: Z
IL Incurred: -W
Net Return: Z - W
```

**Cohort performance benchmarks:**
- **7-day cohort:** Should be near breakeven (fees ≈ IL)
- **30-day cohort:** Should be net positive (+2% to +5%)
- **90-day cohort:** Should clearly outperform holding (+5% to +15%)

**Red flag:** If multiple cohorts show net losses, pool is LP-hostile

### 4. Fee Revenue vs. Token Performance

**Correlation analysis:**

**High positive correlation (>0.7):**
- Volume spikes with price increases
- Indicates: Speculation-driven, FOMO trading
- Risk: Volume collapses in downturns

**Low correlation (<0.3):**
- Steady volume regardless of price
- Indicates: Utility-driven, real usage
- Benefit: Sustainable fee revenue

**Negative correlation (<-0.5):**
- Volume increases when price drops
- Indicates: Panic selling, exit liquidity
- Risk: Death spiral potential

### 5. Capital Efficiency Score

**Weighted pool efficiency vs. concentrated liquidity:**
```
Efficiency Score = (Fees Generated per $1M TVL) / (Benchmark Pool Fees per $1M TVL)

Score > 1.0: Outperforming concentrated liquidity
Score 0.7-1.0: Competitive
Score < 0.7: Losing to concentrated alternatives
```

**Benchmark pools:**
- ETH/USDC on Uniswap v3 (0.05% tier)
- BTC/ETH on Uniswap v3 (0.3% tier)

## Weight-Specific Strategies & Insights

### 80/20 Pools (Governance Tokens)

**Why protocols choose 80/20:**
- Maintain majority ownership while providing liquidity
- Reduce IL exposure by 5x vs. 50/50
- Enable treasury management with less volatility

**LP appeal:**
- Directional bet with liquidity provision income
- Lower IL means longer holding periods make sense
- Often heavily incentivized by protocols

**Analysis focus:**
- Is the protocol actively managing the pool?
- Are incentives sustainable?
- Is the 20% (usually ETH/stable) enough liquidity for traders?
- Monitor for "vampire attacks" (competing pools offering better incentives)

### 50/50 Pools (Equal Weight)

**When 50/50 makes sense:**
- Both tokens equally important
- Maximum fee generation desired
- Neutral directional exposure preferred

**LP appeal:**
- Higher fee generation through constant rebalancing
- Well-understood mechanics (like Uniswap v2)
- Neutral position on both assets

**Analysis focus:**
- Is fee APR competitive with Uni v2/v3?
- Is this the most liquid venue for this pair?
- Capital efficiency vs. concentrated liquidity alternatives

### Multi-Token Pools (Index Funds)

**Use cases:**
- Layer 1 index (ETH/BTC/SOL/AVAX)
- Stablecoin basket (DAI/USDC/USDT/FRAX)
- Sector exposure (DeFi blue chips)

**LP appeal:**
- Single-transaction diversification
- Auto-rebalancing to maintain weights
- Lower gas costs than managing 4+ positions

**Analysis focus:**
- Are weights aligned with market caps or other logical metric?
- Is rebalancing happening automatically (check weight stability)?
- How do fees compare to holding index tokens separately?
- Is there a coherent investment thesis for this basket?

**Fee expectations:**
Lower than 2-token pools due to:
- Less rebalancing per pair
- More complex routing (less direct volume)
- Typically: 0.2-0.4% swap fees, 2-8% APR

## Risk Assessment Framework

### Pool-Specific Risks

**Weight Configuration Risk:**
- **High:** Extreme weights (95/5 or more) create instability
- **Medium:** Weights not aligned with market demand (25/75 in low-liquidity minor token)
- **Low:** Standard configurations with proven market fit (80/20 for governance)

**Impermanent Loss Risk:**
```
Risk Score = (Token Volatility) × (Weight Difference from 50/50) × (Correlation)

Low Risk: <10 (Example: 80/20 stETH/ETH - high correlation)
Medium Risk: 10-30 (Example: 50/50 ETH/USDC)
High Risk: >30 (Example: 50/50 volatile altcoin/stable)
```

**Liquidity Risk:**
```
Liquidity Risk = (Required Swap Size) / (TVL in that token)

Low: <1%
Medium: 1-5%
High: >5%
```

**Concentration Risk:**
```
Concentration Score = (Top 3 LP %) × (1 + LP Gini Coefficient)

Low: <40
Medium: 40-70
High: >70 (potential manipulation)
```

### Market-Level Risks

**Competitive Displacement Risk:**
- Are Uniswap v3 pools taking market share?
- Are newer DEXs offering better incentives?
- Is the pool losing routing priority in aggregators?

**Incentive Sustainability Risk:**
```
Sustainability Score = (Fee APR) / (Total APR)

Sustainable: >50%
At Risk: 30-50%
Unsustainable: <30%
```

**Token-Specific Risks:**
- Regulatory concerns
- Smart contract vulnerabilities
- Team/development activity
- Liquidity across other venues

## Data Quality & Validation

### Cross-Reference Checks

1. **TVL Validation:**
   - On-chain balance × price = Reported TVL?
   - Check against DefiLlama, Dune Analytics
   - Variance >5% = investigate discrepancy

2. **Volume Validation:**
   - Sum of swap events = Reported volume?
   - Cross-check with DEX aggregator data
   - Suspicious: Volume with very few transactions

3. **Weight Validation:**
```
   Actual Weight = (Token Balance × Price) / Total TVL
   Compare to: Reported weight
```

4. **Fee Collection Validation:**
   - Protocol fees being collected correctly?
   - Are LP fees actually accruing?
   - Check swap fee parameter hasn't changed unexpectedly

### Red Flags in Data

🚩 **TVL suddenly jumps 50%+ but volume unchanged:** Possible price oracle manipulation or wash trading

🚩 **Volume extremely high but few unique addresses:** Wash trading or MEV extraction

🚩 **Weights oscillating wildly (±10% daily):** Oracle issues or extreme manipulation

🚩 **Fee APR calculation doesn't match (Fees/TVL):** Data provider error or misreporting

🚩 **All volume in one direction for 7+ days:** Likely coordinated dump or exploit

## Output Framework for Analysis

### Comprehensive Pool Report Structure
```markdown
# [POOL NAME] Analysis Report

## Pool Configuration
- **Type:** Weighted Pool
- **Weights:** X% TOKEN_A / Y% TOKEN_B [/ Z% TOKEN_C]
- **Swap Fee:** N%
- **TVL:** $X.XXM
- **Age:** XX days

## Health Metrics
- **Overall Score:** [0-100]
- **Liquidity Score:** [0-100] (depth, concentration, weight balance)
- **Volume Score:** [0-100] (turnover, directional balance, trend)
- **Profitability Score:** [0-100] (fee APR, IL-adjusted returns)
- **Sustainability Score:** [0-100] (incentive dependency, competitive position)

## Key Statistics (7d/30d/90d)
- **TVL:** $X / $Y / $Z (±%change)
- **Volume:** $X / $Y / $Z (±%change)
- **Turnover:** X% / Y% / Z%
- **Fee APR:** X% / Y% / Z%
- **Unique Traders:** XXX / YYY / ZZZ

## Weight Analysis
- **Current Ratio:** XX.X% / YY.Y%
- **Target Ratio:** XX% / YY%
- **Deviation:** ±X.X%
- **7d Drift Velocity:** ±X.X% per day
- **Status:** ✓ Stable | ⚠ Drifting | 🚨 Critical

## Volume Flow Analysis
- **Directional Balance:**
  - TOKEN_A → TOKEN_B: XX%
  - TOKEN_B → TOKEN_A: YY%
- **Flow Imbalance Score:** ±XX%
- **Interpretation:** [Balanced | Accumulation | Distribution]

## LP Profitability
- **30-day cohort:** ±XX% (fees: +YY%, IL: -ZZ%)
- **90-day cohort:** ±XX% (fees: +YY%, IL: -ZZ%)
- **Benchmark comparison:** [Outperforming | Matching | Underperforming] hold strategy

## Competitive Position
- **Market Share:** XX% of [TOKEN] DEX liquidity
- **Rank:** #X among [similar pools]
- **Fee Efficiency:** [Above | At | Below] category average
- **Incentive Status:** $XXk/month in [BAL/TOKEN] rewards

## Risk Assessment
- **IL Risk:** [Low | Medium | High] - [reasoning]
- **Concentration Risk:** [Low | Medium | High] - Top 3 LPs: XX%
- **Liquidity Risk:** [Low | Medium | High] - $XXk swap = X.X% impact
- **Sustainability Risk:** [Low | Medium | High] - Fee APR XX% vs Total XX%

## Identified Issues
🚨 [Critical issues if any]
⚠ [Warnings if any]
ℹ️ [Notable observations]

## Recommendations

### For Liquidity Providers:
- **Action:** [Enter | Hold | Exit | Rebalance]
- **Reasoning:** [Explanation based on metrics]
- **Optimal Position Size:** [Guidance]
- **Risk-Adjusted Expected APR:** XX-YY%

### For Protocol/Pool Managers:
- **Weight Optimization:** [Keep current | Consider XX/YY]
- **Fee Adjustment:** [Current optimal | Consider X.X%]
- **Incentive Strategy:** [Maintain | Increase | Decrease | Phase out]
- **Additional Recommendations:** [Specific actions]

### For Traders:
- **Liquidity Quality:** [Excellent | Good | Fair | Poor]
- **Recommended Swap Size:** Up to $XXk for <X% impact
- **Best Use Case:** [When to use this pool]

## 30-Day Outlook
- **TVL Trajectory:** [Growing | Stable | Declining]
- **Volume Trend:** [Increasing | Stable | Decreasing]
- **Competitive Threat:** [None | Low | Medium | High]
- **Overall Confidence:** [High | Medium | Low]

## Data Quality Notes
- Last updated: [timestamp]
- Data sources: [list]
- Known limitations: [any gaps or concerns]
```

## Context-Aware Interpretation Examples

### Example 1: 80/20 AURA/ETH Pool

**Given data:**
- TVL: $5M (80.5% AURA / 19.5% ETH)
- 24h Volume: $400k
- Swap Fee: 0.5%
- Fee APR: 15%
- BAL Incentives: 8% APR
- 7d weight drift: 80% → 80.5%

**Analysis:**
✓ Slight weight drift toward AURA (0.5%) suggests mild selling pressure or AURA price decline
✓ Turnover of 8% is healthy for protocol token pool
✓ Fee APR of 15% is competitive even without incentives (65% of total APR from fees)
✓ Sustainable model - could maintain without incentives

**Recommendation:** HOLD/BUY for LPs bullish on AURA with moderate IL protection

### Example 2: 50/50 WETH/USDC Pool

**Given data:**
- TVL: $2M (48% WETH / 52% USDC)
- 24h Volume: $800k
- Swap Fee: 0.2%
- Fee APR: 29%
- No incentives
- Uniswap v3 0.05% tier has $50M TVL

**Analysis:**
⚠ High turnover (40%) but low absolute TVL vs. Uni v3
⚠ Weight imbalance suggests recent ETH price increase
✓ Strong fee APR indicates efficient capital usage
🚨 Major competitive threat - Uni v3 has 25x more liquidity

**Recommendation:** EXIT - capital more efficiently deployed in concentrated liquidity venues unless there's specific routing/composability benefit

### Example 3: 25/25/25/25 L1 Index Pool

**Given data:**
- TVL: $8M (ETH/BTC/SOL/AVAX all ~25%)
- 24h Volume: $120k
- Swap Fee: 0.3%
- Fee APR: 1.6%
- Incentives: 4% APR

**Analysis:**
✓ Weights perfectly balanced - good auto-rebalancing
⚠ Low turnover (1.5%) - pool underutilized
⚠ Majority of APR from incentives (71%)
✓ Provides diversification convenience
🚨 Fee APR below opportunity cost of holding assets separately

**Recommendation:** CONDITIONAL - Only for users who value auto-rebalancing convenience and believe incentives will continue. Otherwise, hold assets separately.

---

## Final Notes for Model Training

When analyzing weighted pools, your model should:

1. **Always contextualize weights** - 80/20 pool behavior is fundamentally different from 50/50
2. **Calculate weight-adjusted IL** - don't use generic IL formulas
3. **Assess directional flow** - volume balance reveals market sentiment
4. **Compare to alternatives** - especially concentrated liquidity pools
5. **Evaluate incentive sustainability** - fee APR should be significant portion of total APR
6. **Consider pool age** - new pools need time to establish, mature pools should be stable
7. **Check for coherent strategy** - weights should make sense for the use case
8. **Validate data quality** - cross-reference on-chain data
9. **Provide actionable insights** - clear recommendations for LPs, protocols, and traders
10. **Acknowledge uncertainty** - use probability language when appropriate ("likely", "suggests", "may indicate")

The goal is not just to report metrics, but to **interpret what they mean** in the context of:
- Pool design (weights, fees)
- Market conditions (volatility, trends)
- Competitive landscape (alternatives, incentives)
- User intent (LP goals, trader needs, protocol objectives)