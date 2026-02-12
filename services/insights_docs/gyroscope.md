# Gyroscope Pools (Balancer / Gyro AMMs) — Specialist Context Pack

## 1) What a Gyroscope Pool is (core intuition)
Gyroscope Pools are **advanced AMMs designed for correlated assets**, where:
- price curves are **anchored by mathematically defined bounds**, and
- liquidity is distributed in a way that **reduces sensitivity to manipulation and sudden shocks**.

Instead of relying purely on a single invariant (like constant product),
Gyro pools use **guardrails** that constrain how prices can move given reserves.

Mental model:
> “A stable-style AMM with *defensive geometry* built into the price curve.”

---

## 2) Why Gyroscope Pools exist
Traditional stable AMMs:
- are capital efficient,
- but can be fragile during depegs, oracle shocks, or adversarial trading.

Gyroscope Pools aim to:
- **limit extreme price deviations**,  
- **reduce exploitability** during low-liquidity or volatile periods,
- maintain **credible pricing even under stress**.

They are especially relevant for:
- stablecoins,
- LSDs / yield-bearing assets,
- assets with strong long-term correlation but short-term noise.

---

## 3) Core design principle: bounded price geometry
Unlike classic AMMs, Gyro pools:
- define **explicit or implicit price bounds**,
- enforce **geometric constraints** that limit how fast or how far prices can move.

Key implication:
- Traders cannot force the pool into absurd prices without supplying *disproportionate liquidity*.
- LPs are protected from sudden reserve-draining attacks.

This makes Gyro pools more:
- conservative,
- predictable,
- resilient to tail-risk events.

---

## 4) Common Gyro variants (high-level)
Exact math differs by implementation, but conceptually:

- **Gyro2 / Gyro3**  
  - Pools with two or three correlated assets
  - Strong emphasis on bounded price deviation

- **E-CLP-style Gyro pools**
  - Concentrated liquidity within a bounded range
  - Similar intuition to “stable + rails”

Agent takeaway:
> Different Gyro pools trade **capital efficiency** for **safety** at different rates.

---

## 5) Return drivers (what produces LP yield)
LP returns typically come from:
1) **Swap fees**
2) **Incentives** (BAL or partner rewards, if enabled)

Important distinction:
- Gyro pools usually **do NOT rely on external yield** by default.
- Returns are more dependent on **volume quality** than passive yield.

---

## 6) Main risks (what can still go wrong)
### 6.1 Correlation breakdown
- Gyro pools assume assets remain *reasonably correlated*.
- If correlation breaks (e.g. partial depeg), bounds protect pricing but:
  - volume can dry up,
  - LPs may hold the weaker asset longer.

### 6.2 Opportunity cost risk
- Defensive curves can:
  - reduce arbitrage profits,
  - reduce fee capture in calm markets.
- LPs may underperform simpler pools when volatility is low and correlation is perfect.

### 6.3 Incentive dependency
- Some Gyro pools rely heavily on incentives to remain attractive.
- Incentive removal can cause rapid TVL exit.

---

## 7) Key pool state variables to track
### Pool fundamentals
- **TVL**
- **Token balances**
- **Swap fee %**
- **Pool type / Gyro variant**

### Price behavior
- **Observed price vs external reference**
- **Price deviation within bounds**
- **Frequency of bound interaction** (how often trades push near limits)

### Trading activity
- **Volume**
- **Fee revenue**
- **Volume / TVL ratio**

---

## 8) Metrics that matter (with interpretation)
### 8.1 Fee APR sustainability
- Fee APR = fees / TVL annualized  
Insight:
- Healthy Gyro pools show **steady fee APR**, not sharp spikes.
- Spiky APR often means short-lived arbitrage events.

---

### 8.2 Price stability under stress
Track:
- max deviation during volatility,
- speed of reversion to equilibrium.

Insight:
- Good Gyro pools absorb shocks with **smaller and slower price moves** than classic AMMs.

---

### 8.3 Capital efficiency vs safety tradeoff
Compare:
- Fee APR per unit of volatility
- Fee APR vs stable or weighted pools with similar assets

Insight:
- Gyro pools often sacrifice peak APR for **tail-risk protection**.

---

### 8.4 Liquidity stickiness
Observe:
- TVL reaction after:
  - volatility spikes,
  - incentive changes,
  - partial depeg events.

Insight:
- Stickier TVL suggests LPs value **defensive design**, not just yield.

---

## 9) Regime-Detection Heuristics (Auto-Labeling Logic)
This section defines **rules the agent should use to decide whether a Gyro pool is “earning its keep.”**

### 9.1 Regime Labels
The agent should classify the pool into one of these regimes:

- **Calm Regime**
- **Stressed Regime**
- **Transitional Regime**

---

### 9.2 Input Signals
The following signals are used for regime detection:

- **Price Deviation**  
  - max deviation from reference price (TWAP / oracle / median market price)

- **Bound Pressure**
  - frequency or duration of trades pushing prices near Gyro bounds

- **Volatility Proxy**
  - rolling std-dev of price
  - or volatility of reference markets

- **Fee Efficiency**
  - Fee APR relative to historical median
  - Volume / TVL ratio

- **TVL Flow**
  - net inflow / outflow during the window

---

### 9.3 Heuristic Rules

#### Calm Regime
Label as **calm** if:
- price deviation is **small and stable**
- bound pressure is **low**
- volatility proxy is **below historical median**
- fee APR is **lower than simpler pools**

Interpretation:
> Gyro safety is underutilized; opportunity cost is present.

Agent message:
- “Pool is operating in a calm regime; defensive design is not being tested.”

---

#### Stressed Regime
Label as **stressed** if:
- price deviation spikes relative to history
- trades frequently approach bounds
- volatility proxy increases sharply
- fee APR remains stable or increases
- TVL does **not** collapse immediately

Interpretation:
> Gyro design is actively protecting LPs.

Agent message:
- “Pool is earning its keep; bounds are absorbing volatility while maintaining pricing.”

---

#### Transitional Regime
Label as **transitional** if:
- volatility or price deviation is rising or falling
- bound pressure increases but does not persist
- fee APR becomes more volatile
- TVL shows early reaction

Interpretation:
> Market is shifting; Gyro advantage may soon appear or fade.

Agent message:
- “Pool is transitioning between calm and stressed regimes.”

---

### 9.4 Cross-Pool Comparison Rule
To validate Gyro value:
- Compare **max price deviation** and **fee stability** against:
  - a classic stable pool,
  - a weighted pool with similar assets.

If Gyro shows:
- lower deviation with similar fee capture → **clear win**
- lower deviation but much lower fees → **defensive premium**
- no deviation difference and lower fees → **underperforming**

---

## 10) Typical insights your agent should generate
### 10.1 “Is the defensive design paying off?”
- Compare Gyro behavior during volatility windows.

Output:
- “During volatility spike X, Gyro pool deviated Y% vs stable pool Z%.”

---

### 10.2 “Is this pool incentive-dependent?”
- Compare organic fee APR vs incentive APR.

Output:
- “Fees represent only N% of total APR → incentive-driven liquidity.”

---

### 10.3 “Who is this pool for right now?”
Classify:
- conservative LPs,
- traders needing predictable execution,
- protocols needing resilient liquidity.

---

## 11) Heuristics / rules of thumb
- Gyro pools shine **during stress**, not perfect correlation.
- Calm markets favor simpler pools.
- Defensive yield is about **risk-adjusted performance**, not peak APR.
- Incentives should be treated as temporary accelerants, not core yield.

---

## 12) Questions the agent should always ask
1) Are assets still strongly correlated?
2) Is price staying comfortably inside bounds?
3) Is fee revenue organic or arbitrage-driven?
4) How incentive-dependent is the TVL?
5) How does this pool compare in stress vs non-Gyro alternatives?

---

## 13) Suggested structured output (agent response)
```json
{
  "headline": "...",
  "pool_regime": "calm | stressed | transitional",
  "fee_apr": "...",
  "incentive_apr": "...",
  "price_stability": {
    "max_deviation": "...",
    "bound_pressure": "low | medium | high"
  },
  "comparables": [...],
  "risks": [...],
  "takeaways": [...]
}
