# Boosted Pools (Balancer) — Specialist Context Pack

## 1) What a Boosted Pool is (in plain terms)
Boosted Pools are **stable-style Balancer pools** (usually built for correlated assets like stablecoins) that:
- keep part of liquidity **directly in the pool (buffer)** for swaps, and
- route the rest into **yield-bearing strategies** (commonly lending markets like Aave, or other vetted wrappers),
so LPs earn:
1) **Swap fees** from trades, plus
2) **External yield** from deployed liquidity, plus sometimes
3) **Incentives** (e.g., BAL/partner rewards depending on chain/period)

Think: “a stable AMM + integrated cash management”.

---

## 2) Why Boosted Pools exist
Stable swaps often have huge TVL and tight prices, but idle liquidity can be underutilized.
Boosted Pools aim to:
- keep **tight pricing and depth** for traders,
- while pushing “idle” funds into **low-risk yield** sources,
- making LP returns more competitive vs. lending directly.

---

## 3) High-level architecture (conceptual)
A Boosted Pool typically has:
- **Pool tokens** (often wrappers of stable assets; exact wrappers depend on the pool)
- A **buffer** (liquidity held in the pool for immediate swaps/withdrawals)
- A **strategy allocation** (liquidity deposited into an external venue like Aave)
- **Rate providers / yield accounting** (the “price” of wrapped tokens grows as yield accrues)

Important implication:
- “TVL” != “deployed capital” (some is buffered, some is earning external yield)

---

## 4) Return components (what drives APR)
Total LP return is usually a blend:
- **External yield APR** (from the strategy)
- **Swap fee APR** (fees collected by trading activity)
- **Incentives APR** (if applicable; can be volatile and time-bound)
- minus any **costs/drag** (buffer drag, rebalancing costs, bad debt events, wrapper fees)

Core mental model:
- If external yield falls, the pool becomes more like a normal stable pool (fees dominate).
- If volume falls, the pool becomes more like a passive yield product (external yield dominates).

---

## 5) Main risks (what can go wrong)
### 5.1 External strategy risk
- Lending market risk (bad debt, oracle issues, governance risk)
- Depeg/asset risk (stablecoins are not risk-free)
- Smart contract risk (wrappers, strategy integration)

### 5.2 Buffer / liquidity risk
- If buffer is too small, swaps may have worse slippage and/or increased reliance on rebalancing.
- In stress events (depeg, high withdrawals), buffer management becomes critical.

### 5.3 Rate / accounting / integration risk
- RateProvider or wrapper accounting errors can distort pricing.
- If a wrapper’s exchange rate moves unexpectedly, it can create arbitrage or mispricing.

### 5.4 “APR illusion” risk
- Quoted boosted APR may include incentives or recent spikes that are not durable.
- External yield is often cyclical (money markets compress fast).

---

## 6) Key onchain / subgraph fields to understand
(Names vary by implementation and data source; these are conceptual.)

### Pool state
- **TVL (Total Value Locked)**
- **Balances per token** (including wrappers)
- **Swap fee %** (and any dynamic fee rules)

### Utilization / deployment
- **Deployed %**: portion of capital in strategy vs buffer
- **Buffer %**: portion held for swaps/withdrawals
- **Net flows**: deposits/withdrawals over time

### Yield components
- **External yield APR** (strategy / wrapper implied rate)
- **Swap fee APR** (fee revenue / TVL annualized)
- **Incentives APR** (if applicable)

### Trading quality
- **Volume**
- **Slippage / price impact proxy** (if you can estimate from trades)
- **Arb dominance** (share of volume likely arbitrage vs organic)

---

## 7) Metrics to interpret (with “how to think about it”)
### 7.1 Boosted APR vs Base APR
- **Boosted APR**: yield-inclusive (external + fees + incentives)
- **Base APR**: often implies “non-boosted” component (commonly fees only; definition can vary)
Insight pattern:
- Large gap between boosted and base suggests **yield is dominating**.
- Narrow gap suggests **fees dominate** or external yields compressed.

### 7.2 Utilization / Deployment Efficiency
- **Deployed Capital / TVL**
- **Buffer Drag** ≈ (1 - deployed%) * external_yield
Insight pattern:
- Very high buffer can mean safer / more liquid, but lower yield.
- Very low buffer can mean higher yield, but stress risk + worse swap experience.

### 7.3 Sustainability (trend + drivers)
- External yield is usually mean-reverting.
- Fees depend on organic volume + volatility + peg stability.
Insight pattern:
- Identify whether APR is trending due to:
  - lending rate changes,
  - volume regime change,
  - incentives starting/ending,
  - major net inflows/outflows.

### 7.4 Concentration risk
- Token concentration (one stable dominates balances)
- Strategy concentration (single venue)
Insight pattern:
- Higher concentration increases tail risk in depeg or venue incidents.

---

## 8) Typical insights your agent should produce (templates)
### 8.1 “Is this return attractive vs alternatives?”
Compare boosted pool’s *sustainable* APR to:
- lending the dominant stable directly on the same venue,
- holding stable in a simpler pool (fees-only),
- other boosted pools with similar risk profile.

Output:
- “After removing incentives, pool yields ~X% vs direct lending ~Y% → premium/discount = Z%”

### 8.2 “What changed recently?”
Detect regime shifts:
- External yield spike/compression
- Volume jump/drop
- Sudden net outflow/inflow
- Deployed % changed (buffer expansion/contraction)

Output:
- “APR fell mainly because external yield dropped from A to B; fees remained flat.”

### 8.3 “Liquidity & stress readiness”
Look for:
- buffer too low for recent withdrawal pressure,
- large imbalance in stable composition,
- depeg sensitivity (if one asset has a history of instability)

Output:
- “Buffer at N% is low given recent net outflows; expect higher slippage risk.”

### 8.4 “Arbitrage vs organic volume”
If volume is high but fees APR doesn’t move much, it may be:
- tight spreads / low fee rate,
- volume dominated by arbitrage with thin margins.

Output:
- “Volume is high but fee APR is modest → likely arb-heavy, low fee capture.”

---

## 9) Heuristics / rules of thumb (use cautiously)
- If **boosted APR ≈ direct lending APR**, then you’re basically getting lending returns with some AMM optionality.
- If **fees APR > external yield APR**, the pool behaves more like a classic stable AMM (volume-driven).
- If **deployed% is high** and **buffer is thin**, returns can look great until a stress event.
- Incentives are the most fragile component; always report APR with and without incentives.

---

## 10) “Questions the agent should ask itself” (self-checklist)
1) What portion of APR is external yield vs fees vs incentives?
2) Is the external yield source stable, or is it clearly in a temporary spike/compression cycle?
3) Is the pool’s buffer level consistent with recent flow/volatility?
4) Are balances concentrated in one token (depeg sensitivity)?
5) Did any parameter change (fee, weights, strategy allocation) explain the shift?
6) What is the best comparable benchmark pool/venue for this exact risk profile?

---

## 11) Output format suggestion (what your specialist returns)
Return a JSON-like object (or structured text) with:
- `headline`: 1-sentence summary
- `apr_breakdown`: { external, fees, incentives, total }
- `utilization`: { deployed_pct, buffer_pct }
- `recent_changes`: [ ... ]
- `risks`: [ ... ]
- `comparables`: [ ... ]
- `actionable_takeaways`: [ ... ]
