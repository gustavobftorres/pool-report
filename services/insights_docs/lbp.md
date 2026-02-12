# Liquidity Bootstrapping Pools (LBPs) — Specialist Context Pack

## 1) What an LBP is (core intuition)
A Liquidity Bootstrapping Pool (LBP) is a **time-varying weighted AMM**, primarily used for:
- **token launches**,
- **price discovery**, and
- **fairer distribution** of new tokens.

An LBP gradually **shifts token weights over time**, usually:
- starting with a **high weight on the project token** (high initial price),
- and decreasing it while increasing the counter-asset weight (e.g. USDC, WETH).

Mental model:
> “A market that *sells price over time* instead of selling tokens at a fixed price.”

---

## 2) Why LBPs exist
Classic token launches suffer from:
- bot domination,
- whales buying early at low prices,
- poor price discovery.

LBPs aim to:
- **discourage early sniping** with high initial prices,
- allow price to **discover organically**,
- reduce the advantage of fast actors,
- let demand reveal itself over time.

LBPs are not designed to maximize LP yield — they are designed to **optimize launch fairness and discovery**.

---

## 3) Core design principle: time-based weight decay
In an LBP:
- weights change **linearly over time** (in most implementations),
- the AMM invariant stays constant,
- the **spot price drifts deterministically** if no trades occur.

Key implication:
- Even with zero volume, **price moves**.
- Traders are interacting with a *moving curve*, not a static one.

This creates:
- downward price pressure over time (for the launched token),
- strategic timing decisions for buyers.

---

## 4) Typical LBP configuration
Common setup:
- **Token A (project token)**  
  - Starts with very high weight (e.g. 90%)
  - Weight decreases over time
- **Token B (raise asset: USDC / WETH)**  
  - Starts with low weight (e.g. 10%)
  - Weight increases over time

Other parameters:
- **Start time / end time**
- **Swap fee**
- **Initial balances**
- Optional:
  - no-protocol-fee variant,
  - post-LBP migration to another pool.

---

## 5) What drives outcomes (LBP “returns”)
Unlike normal pools, LP returns are **not the primary goal**.

Value is determined by:
1) **Demand vs time-decay**
2) **Buy pressure distribution**
3) **Arbitrage behavior**
4) **Final clearing price**

Important:
- Fees are usually secondary.
- The *issuer* is often the main LP and counterparty.

---

## 6) Main risks (what can go wrong)
### 6.1 Weak demand
- If buy pressure does not offset weight-driven price decay:
  - price collapses,
  - poor signaling to market,
  - failed launch perception.

### 6.2 Excessive arbitrage extraction
- Predictable price decay creates arbitrage opportunities.
- If bots dominate:
  - organic users are crowded out,
  - value leaks to arbitrageurs.

### 6.3 Misconfigured parameters
- Too high initial price → no participation.
- Too fast decay → early buyers still advantaged.
- Too low liquidity → volatile price moves.

### 6.4 Illusion of “fairness”
- LBPs reduce but do not eliminate sophisticated actors.
- Poor UX or education can still lead to suboptimal outcomes.

---

## 7) Key state variables to track
### Pool configuration
- Start time / end time
- Initial and final weights
- Swap fee
- Initial balances

### Market behavior
- Price over time
- Volume over time
- Net token outflow (token sold to buyers)
- Counter-asset inflow (capital raised)

### Participant behavior
- Trade size distribution
- Concentration of buyers
- Timing of buys relative to schedule

---

## 8) Metrics that matter (with interpretation)
### 8.1 Price vs deterministic decay
Compare:
- actual price trajectory
- expected price if **no trades occurred**

Insight:
- If actual price stays **above decay curve**, demand is strong.
- If it tracks or falls below decay curve, demand is weak.

---

### 8.2 Buy pressure distribution
Track:
- volume by time bucket,
- clustering of trades.

Insight:
- Healthy LBPs show **distributed buy pressure**.
- Spiky early volume suggests bot/whale dominance.

---

### 8.3 Premium paid vs final price
Compute:
- average purchase price,
- final LBP clearing price.

Insight:
- Large premium indicates strong FOMO.
- Near-clearing buys indicate efficient timing by participants.

---

### 8.4 Capital efficiency
Track:
- funds raised vs initial token allocation.

Insight:
- Reveals whether price curve matched demand elasticity.

---

## 9) Regime-Detection Heuristics (LBP-specific)
LBPs move through **distinct behavioral regimes**.

### 9.1 Regime Labels
- **Overshoot Regime**
- **Healthy Discovery Regime**
- **Decay-Dominated Regime**

---

### 9.2 Input Signals
- Price vs decay baseline
- Buy volume per time bucket
- Trade size concentration
- Net inflow rate
- Arbitrage intensity (rapid buy/sell cycles)

---

### 9.3 Heuristic Rules

#### Overshoot Regime
Label as **overshoot** if:
- price remains far above decay curve,
- volume is concentrated early,
- large trades dominate,
- arbitrage activity is high.

Interpretation:
> Demand is strong but fairness may be compromised.

Agent message:
- “LBP is overshooting; early participants capture most upside.”

---

#### Healthy Discovery Regime
Label as **healthy discovery** if:
- price gradually converges toward equilibrium,
- volume is spread across the timeline,
- no extreme clustering,
- price stabilizes near the end.

Interpretation:
> LBP is functioning as intended.

Agent message:
- “Buy pressure is well distributed; price discovery appears fair.”

---

#### Decay-Dominated Regime
Label as **decay-dominated** if:
- price closely tracks decay curve,
- buy pressure is sparse,
- late-stage buys dominate.

Interpretation:
> Demand is insufficient to counter mechanical price decay.

Agent message:
- “LBP demand is weak; price driven mostly by weight decay.”

---

### 9.4 Cross-LBP Comparison Rule
Compare:
- funds raised per unit time,
- average premium paid,
- buyer concentration.

Insight:
- Effective LBPs show **moderate premium with low concentration**.

---

## 10) Typical insights your agent should generate
### 10.1 “Was this LBP fair?”
- Analyze buy timing and concentration.

Output:
- “Top 5 buyers captured X% of tokens; early clustering detected.”

---

### 10.2 “Did the price curve match demand?”
- Compare decay curve vs realized price.

Output:
- “Price stayed above decay baseline for N% of duration.”

---

### 10.3 “What would improve the next launch?”
- Suggest:
  - slower/faster decay,
  - different initial price,
  - more liquidity,
  - staged LBPs.

---

## 11) Heuristics / rules of thumb
- LBPs sell *time*, not just tokens.
- Mechanical decay without demand guarantees failure.
- Fairness is about **distribution**, not just final price.
- The best LBPs feel “boring” — steady, predictable, no spikes.

---

## 12) Questions the agent should always ask
1) Did demand meaningfully counteract decay?
2) Was volume distributed or clustered?
3) Who captured most of the tokens?
4) Did arbitrage dominate flow?
5) Did the final price look credible post-LBP?

---

## 13) Suggested structured output (agent response)
```json
{
  "headline": "...",
  "lbp_regime": "overshoot | healthy_discovery | decay_dominated",
  "funds_raised": "...",
  "avg_price_paid": "...",
  "final_price": "...",
  "buyer_concentration": "...",
  "price_vs_decay": "...",
  "risks": [...],
  "recommendations": [...]
}
