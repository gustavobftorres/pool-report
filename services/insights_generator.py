"""
Multi-agent insights generator:
- Orchestrator (gpt-4o-mini) routes based on pool type.
- Specialists (gpt-4o) per pool type (stable, weighted, lbp, boosted, gyroscope, reclamm).
- For multi-pool, runs one specialist per pool and then selects a subset of bullets.
"""
import asyncio
import os
from typing import Optional, List, Dict, Any

from openai import AsyncOpenAI

from config import settings
from models import PoolMetrics, MultiPoolMetrics


POOL_TYPE_STABLE = "stable"
POOL_TYPE_WEIGHTED = "weighted"
POOL_TYPE_LBP = "lbp"
POOL_TYPE_BOOSTED = "boosted"
POOL_TYPE_GYROSCOPE = "gyroscope"
POOL_TYPE_RECLAMM = "reclamm"
POOL_TYPE_UNKNOWN = "unknown"


class InsightsGenerator:
    """Service for generating AI-powered insights from pool metrics using a multi-agent pattern."""
    
    def __init__(self):
        """Initialize OpenAI client if API key is available."""
        self.enabled = settings.enable_insights and settings.openai_api_key is not None
        if self.enabled:
            try:
                self.client = AsyncOpenAI(api_key=settings.openai_api_key)
                print("✅ Insights generator enabled (OpenAI API configured)")
            except Exception as e:
                print(f"⚠️  Failed to initialize OpenAI client: {e}")
                self.enabled = False
                self.client = None
        else:
            self.client = None
            if not settings.enable_insights:
                print("ℹ️  Insights generation disabled (ENABLE_INSIGHTS=false)")
            elif not settings.openai_api_key:
                print("ℹ️  Insights generation disabled (OPENAI_API_KEY not set)")
        
        # Model choices
        self.orchestrator_model = settings.openai_orchestrator_model
        self.specialist_model = settings.openai_specialist_model
        self.summarizer_model = settings.openai_summarizer_model
        
        # Docs config
        self.docs_dir = os.path.join("services", "insights_docs")
        self.enable_live_docs = settings.enable_insights_live_docs
        self.docs_base_urls = settings.insights_docs_base_urls or []
        self.max_doc_chars = settings.insights_max_doc_chars
    
    # ------------------------------------------------------------------
    # PUBLIC API (used by Telegram sender)
    # ------------------------------------------------------------------
    async def generate_single_pool_insights(
        self,
        metrics: PoolMetrics,
        pool_data: dict,
        max_bullets: int = 5,
    ) -> str:
        """
        Generate actionable insights for a single pool.
        Returns bullet points as a formatted string.
        
        Args:
            metrics: PoolMetrics object
            pool_data: Pool data dictionary
            max_bullets: Maximum number of bullets to return (default 5)
        """
        if not self.enabled or not self.client:
            return ""
        
        pool_type_key = self._normalize_pool_type(pool_data)
        bullets = await self._run_specialist_for_pool(
            pool_type_key=pool_type_key,
            metrics=metrics,
            pool_data=pool_data,
        )
        # Limit bullets
        bullets = bullets[:max_bullets]
        return self._format_bullets(bullets)
    
    async def generate_multi_pool_insights(
        self,
        metrics: MultiPoolMetrics,
        pools_data: Optional[List[Dict[str, Any]]] = None,
        max_bullets: int = 6,
    ) -> str:
        """
        Generate insights for multiple pools:
        - Runs a specialist per pool (in parallel).
        - Then selects a subset of bullets across pools (selector only, no text editing).
        
        Args:
            metrics: MultiPoolMetrics object
            pools_data: Optional list of pool data dictionaries
            max_bullets: Maximum total bullets to return (default 6)
        """
        if not self.enabled or not self.client:
            return ""
        
        pools_data = pools_data or []
        # Ensure we have same length as metrics.pools where possible
        pool_items: List[Dict[str, Any]] = []
        for idx, pool_metrics in enumerate(metrics.pools):
            pool_info = pools_data[idx] if idx < len(pools_data) else {}
            pool_items.append({
                "metrics": pool_metrics,
                "pool_data": pool_info,
            })
        
        # Run specialists per pool concurrently
        tasks = [
            self._run_specialist_for_pool(
                pool_type_key=self._normalize_pool_type(item["pool_data"]),
                metrics=item["metrics"],
                pool_data=item["pool_data"],
            )
            for item in pool_items
        ]
        
        try:
            per_pool_bullets: List[List[str]] = await asyncio.gather(*tasks)
        except Exception as e:
            print(f"⚠️  Error running multi-pool specialists: {e}")
            return ""
        
        # Wrap with metadata for selection
        pool_bullets_struct = []
        for pool_metrics, bullets in zip(metrics.pools, per_pool_bullets):
            pool_bullets_struct.append(
                {
                    "pool_name": pool_metrics.pool_name,
                    "pool_type": pool_metrics.pool_type,
                    "bullets": bullets,
                }
            )
        
        # Selector-only summarizer: chooses subset of bullets without editing text
        selected_bullets = self._select_portfolio_highlights(pool_bullets_struct, max_bullets=max_bullets)
        return self._format_bullets(selected_bullets)
    
    # ------------------------------------------------------------------
    # Orchestrator + specialists
    # ------------------------------------------------------------------
    def _normalize_pool_type(self, pool_data: Dict[str, Any]) -> str:
        """Map raw pool type into one of our canonical categories."""
        raw_type = (pool_data.get("type") or pool_data.get("poolType") or "").upper()
        if not raw_type:
            return POOL_TYPE_UNKNOWN
        
        if "STABLE" in raw_type:
            return POOL_TYPE_STABLE
        if "WEIGHTED" in raw_type:
            return POOL_TYPE_WEIGHTED
        if "LBP" in raw_type or "LIQUIDITY_BOOTSTRAPPING" in raw_type:
            return POOL_TYPE_LBP
        if "BOOSTED" in raw_type:
            return POOL_TYPE_BOOSTED
        if "GYRO" in raw_type:
            return POOL_TYPE_GYROSCOPE
        if "RECLAMM" in raw_type or "LVR" in raw_type:
            return POOL_TYPE_RECLAMM
        
        return POOL_TYPE_UNKNOWN
    
    async def _run_specialist_for_pool(
        self,
        pool_type_key: str,
        metrics: PoolMetrics,
        pool_data: Dict[str, Any],
    ) -> List[str]:
        """
        Orchestrator + specialist for a single pool.
        Returns a list of bullets (plain strings).
        """
        # For now, orchestrator is a simple mapping; can be extended with gpt-4o-mini routing later.
        specialist_name = pool_type_key or POOL_TYPE_UNKNOWN
        
        # Load curated docs snippet
        docs_snippet = self._load_pool_type_docs(specialist_name)
        
        # Optionally, we could extend with live docs here (hybrid mode).
        live_docs = ""
        if self.enable_live_docs:
            # Placeholder for possible future live fetching
            live_docs = ""
        
        # Build prompt for specialist
        prompt_context = self._format_single_pool_metrics(metrics, pool_data)
        prompt_docs = docs_snippet
        if live_docs:
            prompt_docs = docs_snippet + "\n\nAdditional context:\n" + live_docs
        
        return await self._call_specialist_model(
            pool_type_key=specialist_name,
            docs_snippet=prompt_docs,
            metrics_text=prompt_context,
        )
    
    async def _call_specialist_model(
        self,
        pool_type_key: str,
        docs_snippet: str,
        metrics_text: str,
    ) -> List[str]:
        """Call the specialist model for a given pool type."""
        if not self.enabled or not self.client:
            return []
        
        system_prompt = (
            "You are a DeFi analyst specializing in Balancer pool type '{pool_type}'. "
            "You provide actionable recommendations for pool administrators. "
            "Your insights must include specific numerical values (percentages, dollar amounts, thresholds) "
            "and clear actions that pool admins should take. "
            "Return only plain text bullet points, one per line, without markdown symbols."
        ).format(pool_type=pool_type_key)
        
        user_prompt = (
            f"Balancer docs (summary for this pool type):\n{docs_snippet}\n\n"
            f"Pool metrics and context:\n{metrics_text}\n\n"
            "Produce 4 concise bullet points with actionable recommendations for the pool administrator. "
            "Each bullet MUST:\n"
            "- Include specific numerical values (e.g., 'increase swap fee to 0.05%', 'target TVL of $500K', 'if volume drops below $10K/day')\n"
            "- Focus on actions the admin can take (e.g., 'adjust weights', 'modify swap fee', 'monitor rebalance frequency')\n"
            "- Be quantitative and data-driven\n"
            "- Be on its own line\n"
            "- NOT start with '-', '*', or '•'"
        )
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.specialist_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=400,  # Increased for more detailed numerical recommendations
                ),
                timeout=12.0,
            )
        except asyncio.TimeoutError:
            print("⚠️  Specialist model timeout - skipping insights for this pool")
            return []
        except Exception as e:
            print(f"⚠️  Error calling specialist model: {e}")
            return []
        
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return []
        
        # Convert to clean bullet list
        bullets: List[str] = []
        for line in content.split("\n"):
            text = line.strip()
            if not text:
                continue
            text = text.lstrip("•-* ").strip()
            if text:
                bullets.append(text)
        return bullets
    
    # ------------------------------------------------------------------
    # Selection-only summarizer for multi-pool insights
    # ------------------------------------------------------------------
    def _select_portfolio_highlights(self, pool_bullets_struct: List[Dict[str, Any]], max_bullets: int = 6) -> List[str]:
        """
        Select a subset of bullets across pools without editing them.
        Strategy:
        - Take up to 2 bullets per pool in order, until a global cap.
        - Prepend pool name to each bullet for context.
        
        Args:
            pool_bullets_struct: List of dicts with pool_name, pool_type, bullets
            max_bullets: Maximum total bullets to return
        """
        max_per_pool = 2
        selected: List[str] = []
        
        for entry in pool_bullets_struct:
            pool_name = entry.get("pool_name", "Pool")
            bullets: List[str] = entry.get("bullets") or []
            for bullet in bullets[:max_per_pool]:
                if len(selected) >= max_bullets:
                    break
                # Do not edit bullet text, only prefix with pool name
                selected.append(f"{pool_name}: {bullet}")
            if len(selected) >= max_bullets:
                break
        
        return selected
    
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_pool_type_docs(self, pool_type_key: str) -> str:
        """Load curated markdown snippet for a pool type."""
        mapping = {
            POOL_TYPE_STABLE: "stable.md",
            POOL_TYPE_WEIGHTED: "weighted.md",
            POOL_TYPE_LBP: "lbp.md",
            POOL_TYPE_BOOSTED: "boosted.md",
            POOL_TYPE_GYROSCOPE: "gyroscope.md",
            POOL_TYPE_RECLAMM: "reclamm.md",
        }
        filename = mapping.get(pool_type_key, None)
        if not filename:
            return "General Balancer pool: provide high-level, generic insights using the metrics."
        
        path = os.path.join(self.docs_dir, filename)
        if not os.path.exists(path):
            return "General Balancer pool: provide high-level, generic insights using the metrics."
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                if len(content) > self.max_doc_chars:
                    content = content[: self.max_doc_chars]
                return content
        except Exception as e:
            print(f"⚠️  Could not read docs for {pool_type_key}: {e}")
            return "General Balancer pool: provide high-level, generic insights using the metrics."
    
    def _format_single_pool_metrics(self, metrics: PoolMetrics, pool_data: dict) -> str:
        """Format single pool metrics into a readable text format."""
        lines = [
            f"Pool Name: {metrics.pool_name}",
            f"Pool Type: {metrics.pool_type}",
            f"Swap Fee: {metrics.swap_fee * 100:.4f}%",  # Convert decimal to percentage (0.00322 -> 0.322%)
            f"Core Pool: {'Yes' if metrics.is_core_pool else 'No'}",
            "",
            f"TVL: ${metrics.tvl_current:,.2f} (Change: {metrics.tvl_change_percent:+.2f}% from 15 days ago)",
            f"Volume (15d): ${metrics.volume_15_days:,.2f} (Change: {metrics.volume_change_percent:+.2f}%)",
            f"Fees (15d): ${metrics.fees_15_days:,.2f} (Change: {metrics.fees_change_percent:+.2f}%)",
            f"APR: {metrics.apr_current * 100:.2f}%" if metrics.apr_current else "APR: N/A",
        ]
        
        # Add pool-type specific metrics
        if metrics.token_weights:
            weights_str = ", ".join([f"{token}: {weight:.1f}%" for token, weight in metrics.token_weights.items()])
            lines.append(f"Token Weights: {weights_str}")
        
        if metrics.boosted_apr is not None:
            lines.append(f"Boosted APR: {metrics.boosted_apr * 100:.2f}%")
            if metrics.boosted_apr_15d_ago is not None and metrics.boosted_apr_15d_ago != 0:
                change = ((metrics.boosted_apr - metrics.boosted_apr_15d_ago) / metrics.boosted_apr_15d_ago) * 100
                lines.append(f"Boosted APR Change: {change:+.2f}%")
        
        if metrics.surge_fees is not None:
            lines.append(f"Surge Hook Fees: ${metrics.surge_fees:,.2f}")
            if metrics.surge_fees_15d_ago is not None and metrics.surge_fees_15d_ago != 0:
                change = ((metrics.surge_fees - metrics.surge_fees_15d_ago) / metrics.surge_fees_15d_ago) * 100
                lines.append(f"Surge Fees Change: {change:+.2f}%")
        
        if metrics.rebalance_count_15d is not None:
            lines.append(f"Rebalance Count (15d): {metrics.rebalance_count_15d}")
        
        return "\n".join(lines)
    
    def _format_bullets(self, bullets: List[str]) -> str:
        """Format a list of plain-text bullets into a string with '• ' prefix."""
        if not bullets:
            return ""
        return "\n".join(f"• {b}" for b in bullets)
