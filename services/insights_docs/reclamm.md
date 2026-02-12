# reCLAMM Pools (Balancer) — Specialist Context Pack

## 1) What a reCLAMM Pool is (core intuition)
A reCLAMM pool is a **rebalancing Concentrated Liquidity AMM**, designed to:
- maintain liquidity **concentrated around a moving target price**, and
- **automatically reposition** liquidity as market conditions change.

Unlike static CLAMMs (fixed price ranges), reCLAMM pools:
- **adapt their liquidity distribution over time**, and
- aim to stay capital-efficient **without requiring manual LP management**.

Mental model:
> “Concentrated liquidity that *follows the market* instead of waiting for the market to come back.”

---

## 2) Why reCLAMM pools exist
Classic AMMs:
- waste capital far from the market price.

Static CLAMMs:
- are capital efficient,
- but require active management,
- and become inactive when price exits the range.

reCLAMM pools aim to:
- **retain CL-like efficiency**,  
- while reducing LP operational overhead,
- and minimizing “dead liquidity” periods.

They are especially suited for:
- assets with **persistent price drift**,
- volatile but liquid pairs,
- environments where passive LPs want efficiency without micromanagement.

---

## 3) Core design principle: adaptive liquidity re-centering
reCLAMM pools define:
- a **liquidity distribution function** around a reference price,
- and a **rebalancing rule** that shifts this distribution over time.

Key implication:
- Liquidity follows the market price **within predefined constraints**.
- LP exposure is continuously reshaped, not fixed.

This creates:
- higher fee capture per unit of TVL,
- reduced inactive liquidity,
- implicit trading against trends.

---

## 4) High-level architecture (conceptual)
A reCLAMM pool consists of:
- a **concentrated liquidity curve**,
- a **reference price** (oracle, TWAP, or internal signal),
- a **rebalancing cadence** (continuous or discrete),
- constraints to avoid excessive churn or manipulation.

Important:
- Rebalancing is **not free** — it introduces implicit costs and risk.

---

## 5) Return drivers (what produces LP yield)
LP returns are driven by:
1) **Swap fees captured near the active price**
2) **Capital efficiency** (fees per unit TVL)
3) Optional **incentives** (if configured)

Key distinction:
- reCLAMM yield depends heavily on **price path and volatility**, not just volume.

---

## 6) Main risks (what can go wrong)
### 6.1 Trend-following risk
- If price trends strongly in one direction:
  - reCLAMM may repeatedly rebalance,
  - effectively selling into strength or buying into weakness.

This can:
- reduce net asset value relative to holding.

---

### 6.2 Rebalancing cost / drag
- Frequent repositioning can:
  - dilute gains,
  - amplify losses in choppy markets.

Key tradeoff:
> Adaptivity vs churn.

---

### 6.3 Oracle / reference price risk
- If the reference price is manipulated or lags:
  - liquidity may be positioned inefficiently,
  - attackers can extract value.

---

### 6.4 Volatility mismatch
- Low volatility → underutilized adaptivity.
- Extremely high volatility → excessive repositioning.

---

## 7) Key state variables to track
### Pool configuration
- Concentration width
- Rebalancing frequency / sensitivity
- Reference price source
- Swap fee %

### Market behavior
- Spot price vs reference price
- Volatility regime
- Volume near active range

### Liquidity behavior
- Active liquidity %
- Rebalancing events (count & magnitude)
- Effective liquidity drift

---

## 8) Metrics that matter (with interpretation)
### 8.1 Fee efficiency
- **Fee APR per unit of active liquidity**

Insight:
- reCLAMM pools should outperform static pools *on efficiency*, not necessarily on raw APR.

---

### 8.2 Rebalancing intensity
Track:
- number of re-centering events,
- average price movement per rebalance.

Insight:
- High intensity with low fee capture suggests **churn-dominated regime**.

---

### 8.3 Price tracking quality
Measure:
- distance between reference price and realized price.

Insight:
- Large persistent gaps indicate oracle lag or misconfiguration.

---

### 8.4 Capital utilization
Compare:
- active liquidity vs total TVL.

Insight:
- High utilization confirms reCLAMM advantage over static CLAMMs.

---

## 9) Regime-Detection Heuristics (reCLAMM-specific)
reCLAMM performance is highly **regime-dependent**.

### 9.1 Regime Labels
- **Trending Regime**
- **Mean-Reverting Regime**
- **Choppy / Noise Regime**

---

### 9.2 Input Signals
- Price trend slope
- Volatility
- Rebalancing frequency
- Fee APR stability
- Net asset drift vs HODL

---

### 9.3 Heuristic Rules

#### Trending Regime
Label as **trending** if:
- price shows sustained directional movement,
- frequent rebalancing occurs,
- fee APR does not compensate drift losses.

Interpretation:
> reCLAMM is fighting the trend.

Agent message:
- “Strong directional trend detected; rebalancing drag likely.”

---

#### Mean-Reverting Regime
Label as **mean-reverting** if:
- price oscillates within a band,
- rebalancing frequency is moderate,
- fee APR is high and stable.

Interpretation:
> Ideal environment for reCLAMM.

Agent message:
- “Market oscillation favors adaptive liquidity; efficiency maximized.”

---

#### Choppy / Noise Regime
Label as **choppy** if:
- price whipsaws,
- rebalancing is frequent,
- fee capture is inconsistent.

Interpretation:
> Repositioning cost dominates.

Agent message:
- “Market noise causing excessive churn.”

---

### 9.4 Cross-Pool Comparison Rule
Compare reCLAMM vs:
- static CL pool,
- weighted pool,
- Gyro pool (if correlated assets).

Insight:
- reCLAMM should win on **fee efficiency in mean-reverting markets**.

---

## 10) Typical insights your agent should generate
### 10.1 “Is adaptivity helping or hurting?”
- Compare fee capture vs rebalancing drag.

Output:
- “Adaptive re-centering increased fee efficiency but reduced NAV by X%.”

---

### 10.2 “Is the pool well-configured?”
- Evaluate concentration width vs volatility.

Output:
- “Current width too narrow for observed volatility.”

---

### 10.3 “Who is this pool best for?”
Classify:
- passive LPs seeking efficiency,
- traders needing deep liquidity near price,
- protocols requiring adaptive liquidity.

---

## 11) Heuristics / rules of thumb
- reCLAMM excels in **sideways, liquid markets**.
- Strong trends favor holding or static exposure.
- Too much adaptivity can be as bad as too little.
- Fee efficiency matters more than headline APR.

---

## 12) Questions the agent should always ask
1) Is price trending or mean-reverting?
2) Is rebalancing frequency proportional to volatility?
3) Are fees compensating re-centering costs?
4) Is the reference price reliable?
5) Would a simpler pool outperform in this regime?

---

## 13) Suggested structured output (agent response)
```json
{
  "headline": "...",
  "market_regime": "trending | mean_reverting | choppy",
  "fee_apr": "...",
  "rebalancing_intensity": "...",
  "capital_utilization": "...",
  "nav_vs_hodl": "...",
  "risks": [...],
  "recommendations": [...]
}
