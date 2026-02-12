"""
Multi-agent insights generator:
- Orchestrator (gpt-4o-mini) routes based on pool type.
- Specialists (gpt-4o) per pool type (stable, weighted, lbp, boosted, gyroscope, reclamm).
- For multi-pool, runs one specialist per pool and then selects a subset of bullets.
"""
import asyncio
import json
import os
import logging
from typing import Optional, List, Dict, Any

from openai import AsyncOpenAI

from config import settings
from models import PoolMetrics, MultiPoolMetrics
from services.dex_benchmarker import DEXBenchmarker
from services.dune_metrics import METRIC_GROUP_NAMES, DuneMetricsService
logger = logging.getLogger(__name__)


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

        # DEX benchmarking
        self.dex_benchmarker = DEXBenchmarker()
        
        # Dune metrics service for AI tool access
        self.dune_service = DuneMetricsService()
    
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
        
        # Fetch competitor benchmarks (best-effort)
        competitor_data = await self._fetch_competitor_context(pool_data)

        pool_type_key = self._normalize_pool_type(pool_data)
        bullets = await self._run_specialist_for_pool(
            pool_type_key=pool_type_key,
            metrics=metrics,
            pool_data=pool_data,
            competitor_data=competitor_data,
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
        
        # Fetch competitor benchmarks per pool (best-effort), concurrently
        competitor_results = await self._fetch_competitors_for_pools(pool_items)

        # Run specialists per pool concurrently
        tasks = [
            self._run_specialist_for_pool(
                pool_type_key=self._normalize_pool_type(item["pool_data"]),
                metrics=item["metrics"],
                pool_data=item["pool_data"],
                competitor_data=competitor_results.get(idx, {}),
            )
            for idx, item in enumerate(pool_items)
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
        competitor_data: Optional[Dict[str, Any]] = None,
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
            competitor_data=competitor_data or {},
        )
    
    async def _call_specialist_model(
        self,
        pool_type_key: str,
        docs_snippet: str,
        metrics_text: str,
        competitor_data: Dict[str, Any],
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
        
        competitor_section = "No competitor data available; focus on Balancer metrics only."
        if competitor_data:
            fee_range = competitor_data.get("fee_range") or {}
            min_fee = fee_range.get("min_fee")
            med_fee = fee_range.get("median_fee")
            max_fee = fee_range.get("max_fee")
            total_vol = competitor_data.get("total_volume_24h")
            competitors = competitor_data.get("competitors") or []
            competitor_lines = []
            for c in competitors:
                competitor_lines.append(
                    f"- {c.get('dex') or 'DEX'}: fee={c.get('swap_fee')} vol24h={c.get('volume_24h')} liq={c.get('liquidity')}"
                )
            competitor_section = (
                "Competitor benchmarks (top DEXes):\n"
                f"Fee range: {min_fee} – {max_fee} (median {med_fee})\n"
                f"Total competitor 24h volume: {total_vol}\n"
                + "\n".join(competitor_lines)
            )

        user_prompt = (
            f"Balancer docs (summary for this pool type):\n{docs_snippet}\n\n"
            f"Pool metrics and context:\n{metrics_text}\n\n"
            f"{competitor_section}\n\n"
            "Produce 4 concise bullet points with actionable recommendations for the pool administrator. "
            "Each bullet MUST:\n"
            "- Include specific numerical values (e.g., 'increase swap fee to 0.05%', 'target TVL of $500K', 'if volume drops below $10K/day')\n"
            "- Compare to competitor fee/volume where relevant (e.g., 'increase fee from X to Y–Z%, still below median competitor fee')\n"
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
    

    async def _fetch_competitor_context(self, pool_data: dict) -> Dict[str, Any]:
        """Best-effort fetch of competitor benchmarks for a single pool."""
        try:
            network = self._normalize_network(pool_data)
            tokens = self._extract_tokens_for_benchmark(pool_data)
            if len(tokens) < 2:
                return {}
            token_a, token_b = tokens[0], tokens[1]
            return await self.dex_benchmarker.fetch_competitors(network, token_a, token_b)
        except Exception as e:
            logger.warning("DEXBenchmarker single-pool fallback: %s", e)
            return {}

    async def _fetch_competitors_for_pools(self, pool_items: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """Fetch competitor data per pool (parallel, best-effort)."""
        results: Dict[int, Dict[str, Any]] = {}
        tasks = []
        for idx, item in enumerate(pool_items):
            pool_data = item.get("pool_data") or {}
            tokens = self._extract_tokens_for_benchmark(pool_data)
            network = self._normalize_network(pool_data)
            if len(tokens) >= 2:
                token_a, token_b = tokens[0], tokens[1]
                tasks.append(
                    self.dex_benchmarker.fetch_competitors(network, token_a, token_b)
                )
            else:
                tasks.append(asyncio.sleep(0, result={}))
        
        try:
            fetched = await asyncio.gather(*tasks)
            for idx, data in enumerate(fetched):
                results[idx] = data
        except Exception as e:
            logger.warning("DEXBenchmarker multi-pool fallback: %s", e)
        return results

    def _normalize_network(self, pool_data: Dict[str, Any]) -> str:
        """Map pool data or settings to a GeckoTerminal network slug."""
        raw = (pool_data.get("_blockchain") or settings.blockchain_name or settings.default_chain or "ethereum").lower()
        network_map = {
            "mainnet": "eth",
            "ethereum": "eth",
            "eth": "eth",
            "arbitrum": "arbitrum",
            "polygon": "polygon",
            "optimism": "optimism",
            "base": "base",
        }
        return network_map.get(raw, raw)

    def _extract_tokens(self, pool_data: Dict[str, Any]) -> List[str]:
        """Extract token addresses from pool data (raw)."""
        tokens = pool_data.get("allTokens") or pool_data.get("displayTokens") or pool_data.get("tokens") or []
        addrs = []
        for t in tokens:
            addr = t.get("address") or t.get("tokenAddress")
            if addr:
                addrs.append(addr.lower())
        # Deduplicate, keep order
        seen = set()
        deduped = []
        for a in addrs:
            if a not in seen:
                seen.add(a)
                deduped.append(a)
        return deduped

    def _extract_tokens_for_benchmark(self, pool_data: Dict[str, Any]) -> List[str]:
        """
        Extract *benchmark* token addresses (prefer 2 core ERC-20 tokens, skip BPT/LP-like tokens).
        This prevents accidentally choosing internal/BPT-like tokens that won't resolve on GeckoTerminal.
        """
        tokens = pool_data.get("allTokens") or pool_data.get("displayTokens") or pool_data.get("tokens") or []
        candidates: List[str] = []
        for t in tokens:
            symbol = (t.get("symbol") or "").upper()
            addr = (t.get("address") or t.get("tokenAddress") or "").lower()
            if not addr:
                continue
            # Skip obvious pool/BPT/LP tokens
            if "BPT" in symbol or symbol in {"BPT", "BALANCER", "POOL"}:
                continue
            candidates.append(addr)

        # Deduplicate, keep order; return first 2
        seen = set()
        result = []
        for a in candidates:
            if a not in seen:
                seen.add(a)
                result.append(a)
            if len(result) >= 2:
                break
        return result

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
    
    async def generate_dune_metrics_insights(
        self,
        pipeline_results: Dict[str, Any],
        max_bullets: int = 5,
    ) -> str:
        """
        Generate actionable insights from Dune metrics pipeline results.
        
        Analyzes the input pool against competitors using 8 metric groups from Dune.
        Provides AI with tool access to fetch additional data if needed.
        
        Args:
            pipeline_results: Results dictionary from MetricsPipeline.analyze_pool_with_competitors()
                Format: {
                    "input_pool": {
                        "pool_address": str,
                        "pool_name": str,
                        "dex": str,
                        "blockchain": str,
                        "metrics": {metric_group: {rows: [...], error: ...}}
                    },
                    "competitors": [
                        {
                            "pool_address": str,
                            "pool_name": str,
                            "dex": str,
                            "blockchain": str,
                            "metrics": {metric_group: {rows: [...], error: ...}}
                        },
                        ...
                    ]
                }
            max_bullets: Maximum number of insights to return
            
        Returns:
            Formatted string with bullet-point insights
        """
        if not self.enabled or not self.client:
            return ""
        
        input_pool = pipeline_results.get("input_pool")
        if not input_pool:
            return ""
        
        # Get pool data (we need it for pool type detection)
        pool_data = {
            "name": input_pool.get("pool_name", "Unknown"),
            "address": input_pool.get("pool_address"),
            "type": input_pool.get("dex", "Unknown"),
        }
        
        # Format input pool metrics
        input_metrics_text = self._format_dune_metrics(input_pool.get("metrics", {}))
        
        # Format competitor comparison (with full metrics)
        competitors = pipeline_results.get("competitors", [])
        competitor_comparison = self._format_competitor_comparison(competitors)
        
        # Detect pool type (try to infer from DEX or use unknown)
        pool_type_key = self._normalize_pool_type(pool_data)
        
        # Load specialist docs
        docs_snippet = self._load_pool_type_docs(pool_type_key)
        
        # Load metrics documentation
        metrics_docs = self._load_metrics_docs()
        
        # Build and call specialist with comparative prompt and tool access
        bullets = await self._call_specialist_model_comparative(
            pool_type_key=pool_type_key,
            pool_name=input_pool.get("pool_name", "Unknown"),
            pool_dex=input_pool.get("dex", "Unknown"),
            pool_address=input_pool.get("pool_address", ""),
            blockchain=input_pool.get("blockchain", "ethereum"),
            input_metrics_text=input_metrics_text,
            competitor_comparison=competitor_comparison,
            docs_snippet=docs_snippet,
            metrics_docs=metrics_docs,
        )
        
        # Limit bullets
        bullets = bullets[:max_bullets]
        return self._format_bullets(bullets)
    
    def _format_dune_metrics(self, metrics: Dict[str, Any]) -> str:
        """
        Format Dune metrics dictionary into readable text for LLM.
        
        Args:
            metrics: Dictionary with metric groups as keys
                Format: {
                    "demand_usage": {"rows": [...], "error": ...},
                    "liquidity_depth": {"rows": [...], "error": ...},
                    ...
                }
        
        Returns:
            Formatted text string
        """
        lines = []
        
        for metric_group, group_name in METRIC_GROUP_NAMES.items():
            if metric_group not in metrics:
                continue
            
            metric_data = metrics[metric_group]
            lines.append(f"\n=== {group_name} ===")
            
            # Check for errors
            if "error" in metric_data:
                lines.append(f"Error: {metric_data['error']}")
                continue
            
            # Format rows
            rows = metric_data.get("rows", [])
            if not rows:
                lines.append("No data available")
                continue
            
            # Format first few rows (limit to avoid token limits)
            for i, row in enumerate(rows[:5]):  # Limit to 5 rows per metric group
                if isinstance(row, dict):
                    # Format as key-value pairs
                    row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                    lines.append(f"  {row_str}")
                else:
                    lines.append(f"  {row}")
            
            if len(rows) > 5:
                lines.append(f"  ... ({len(rows) - 5} more rows)")
        
        return "\n".join(lines)
    
    def _format_competitor_comparison(self, competitors: List[Dict[str, Any]]) -> str:
        """
        Format competitor pools for comparative analysis with full metrics.
        
        Args:
            competitors: List of competitor pool dictionaries with metrics
        
        Returns:
            Formatted text string for LLM context with detailed metrics
        """
        if not competitors:
            return "No competitor pools available for comparison."
        
        lines = [
            f"Competitor Analysis: {len(competitors)} competitor pools found",
            ""
        ]
        
        for i, competitor in enumerate(competitors, 1):
            pool_name = competitor.get("pool_name", "Unknown")
            dex = competitor.get("dex", "Unknown")
            pool_address = competitor.get("pool_address", "Unknown")
            blockchain = competitor.get("blockchain", "Unknown")
            
            lines.append(f"=== Competitor {i}: {pool_name} ({dex}) ===")
            lines.append(f"Address: {pool_address}")
            lines.append(f"Blockchain: {blockchain}")
            lines.append("")
            
            # Format full metrics for competitor (same as input pool)
            metrics = competitor.get("metrics", {})
            competitor_metrics_text = self._format_dune_metrics(metrics)
            lines.append(competitor_metrics_text)
            lines.append("")  # Empty line between competitors
        
        return "\n".join(lines)
    
    async def _call_specialist_model_comparative(
        self,
        pool_type_key: str,
        pool_name: str,
        pool_dex: str,
        pool_address: str,
        blockchain: str,
        input_metrics_text: str,
        competitor_comparison: str,
        docs_snippet: str,
        metrics_docs: str,
    ) -> List[str]:
        """
        Call specialist model with comparative analysis prompt and tool access.
        
        Args:
            pool_type_key: Pool type for specialist selection
            pool_name: Name of the input pool
            pool_dex: DEX name of the input pool
            pool_address: Pool address for API calls
            blockchain: Blockchain name for API calls
            input_metrics_text: Formatted metrics text for input pool
            competitor_comparison: Formatted competitor comparison text
            docs_snippet: Specialist documentation snippet
            metrics_docs: Metrics documentation explaining all Dune metrics
        
        Returns:
            List of insight bullet points
        """
        if not self.enabled or not self.client:
            return []
        
        # Define tools (functions) for the AI to call
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "fetch_dune_metrics",
                    "description": (
                        "Fetch additional metrics from Dune Analytics for a specific pool. "
                        "Use this to get more detailed data for any pool (input or competitor) if you need deeper analysis. "
                        "Returns all 8 metric groups: demand_usage, liquidity_depth, fee_monetization, "
                        "capital_efficiency, lp_outcome, behavioral_market_power, comparative_positioning, volume_depth_unit."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pool_address": {
                                "type": "string",
                                "description": "The pool address to query (e.g., '0x3de27efa2f1aa663ae5d458857e731c129069f29')"
                            },
                            "blockchain": {
                                "type": "string",
                                "description": "Blockchain name (e.g., 'ethereum', 'arbitrum', 'polygon')",
                                "enum": ["ethereum", "arbitrum", "polygon", "optimism", "base"]
                            },
                            "dex": {
                                "type": "string",
                                "description": "DEX name for the pool",
                                "enum": ["Balancer", "UniSwap", "Curve", "Fluid", "PancakeSwap"]
                            },
                            "main_token_symbol": {
                                "type": "string",
                                "description": "Optional: Main token symbol (required for comparative_positioning queries)"
                            }
                        },
                        "required": ["pool_address", "blockchain", "dex"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_gecko_competitors",
                    "description": (
                        "Fetch competitor pools from GeckoTerminal API for a given token. "
                        "Use this to find additional competitor pools or get more details about existing competitors. "
                        "Returns pools containing the specified token paired with any other token."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "network": {
                                "type": "string",
                                "description": "Network slug (e.g., 'eth', 'arbitrum', 'polygon')"
                            },
                            "token_address": {
                                "type": "string",
                                "description": "Token address to search for (will find pools containing this token)"
                            },
                            "top_n": {
                                "type": "integer",
                                "description": "Number of top pools to return (default: 3)",
                                "default": 3
                            }
                        },
                        "required": ["network", "token_address"]
                    }
                }
            }
        ]
        
        system_prompt = (
            "You are an expert DeFi analyst specializing in deep DEX pool analysis. "
            "You analyze pools across multiple DEXes (Balancer, UniSwap, Curve, Fluid, PancakeSwap) "
            "using 8 comprehensive metric groups: Demand/Usage, Liquidity & Depth, Fee & Monetization, "
            "Capital Efficiency, LP Outcome, Behavioral & Market Power, Comparative Positioning, and Volume Depth Unit. "
            "\n\n"
            "You have access to tools that allow you to:\n"
            "1. Fetch additional Dune metrics for any pool if you need more detailed data\n"
            "2. Search for additional competitor pools via GeckoTerminal API\n"
            "\n"
            "Use these tools proactively if you need more data to provide a comprehensive analysis. "
            "Don't hesitate to fetch additional metrics or find more competitors if it would improve your analysis.\n"
            "\n"
            "Your analysis should be DEEP and COMPREHENSIVE. You must:\n"
            "- Analyze relationships between different metric groups (e.g., how TVL affects price impact, how volume relates to fees)\n"
            "- Compare specific numerical values across competitors (not just general statements)\n"
            "- Identify patterns, anomalies, and opportunities\n"
            "- Provide actionable recommendations with specific targets and thresholds\n"
            "- Reference the metrics documentation to understand what each metric means and how to interpret it\n"
            "- Consider economic relationships (e.g., capital efficiency vs fee generation, risk-adjusted returns)\n"
            "\n"
            "Return only plain text bullet points, one per line, without markdown symbols. "
            "Each bullet should be substantial and data-rich, not superficial."
        )
        
        # Build comprehensive user prompt
        user_prompt_parts = [
            f"Pool Information:",
            f"Pool Name: {pool_name}",
            f"Pool Address: {pool_address}",
            f"DEX: {pool_dex}",
            f"Blockchain: {blockchain}",
            f"Pool Type: {pool_type_key}",
            "",
            "=== METRICS DOCUMENTATION ===",
            "This document explains all the metrics you'll see. Use it to understand what each metric means, "
            "how to interpret it, and how to compare pools effectively:",
            metrics_docs if metrics_docs else "Metrics documentation not available.",
            "",
            "=== POOL TYPE SPECIALIST DOCUMENTATION ===",
            docs_snippet,
            "",
            "=== INPUT POOL METRICS (8 metric groups from Dune Analytics) ===",
            input_metrics_text,
            "",
            "=== COMPETITOR POOLS ANALYSIS ===",
            competitor_comparison,
            "",
            "=== ANALYSIS INSTRUCTIONS ===",
            "Perform a DEEP, COMPREHENSIVE analysis of the input pool compared to competitors. "
            "You have access to tools to fetch additional data if needed.\n"
            "\n"
            "Your analysis should include:\n"
            "1. Quantitative comparisons across all 8 metric groups\n"
            "2. Identification of strengths and weaknesses relative to competitors\n"
            "3. Analysis of relationships between metrics (e.g., how capital efficiency affects LP outcomes)\n"
            "4. Specific numerical targets and thresholds for improvement\n"
            "5. Actionable recommendations with concrete steps\n"
            "\n"
            "If you need more data to provide a thorough analysis, use the available tools:\n"
            "- fetch_dune_metrics: Get detailed metrics for any pool\n"
            "- fetch_gecko_competitors: Find additional competitor pools\n"
            "\n"
            "Provide 5-7 substantial bullet points. Each bullet MUST:\n"
            "- Include specific numerical values from the metrics (percentages, dollar amounts, ratios, etc.)\n"
            "- Compare specific values between input pool and competitors\n"
            "- Reference specific metric groups and explain their significance\n"
            "- Provide actionable recommendations with quantitative targets\n"
            "- Be data-driven and reference the metrics documentation\n"
            "- Be on its own line\n"
            "- NOT start with '-', '*', or '•'"
        ]
        
        user_prompt = "\n".join(user_prompt_parts)
        
        # Execute with tool calling support
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        max_iterations = 5  # Allow multiple tool calls
        iteration = 0
        
        while iteration < max_iterations:
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.specialist_model,
                        messages=messages,
                        tools=tools,
                        tool_choice="auto",  # Let the model decide when to use tools
                        temperature=0.7,
                        max_tokens=1200,  # Increased for comprehensive analysis
                    ),
                    timeout=60.0,  # Increased timeout for tool calls
                )
            except asyncio.TimeoutError:
                logger.warning("Specialist model timeout - skipping insights")
                return []
            except Exception as e:
                logger.warning(f"Error calling specialist model: {e}")
                return []
            
            message = response.choices[0].message
            
            # Add assistant's response to messages
            messages.append(message)
            
            # Check if the model wants to call tools
            if message.tool_calls:
                # Execute tool calls
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse tool arguments: {tool_call.function.arguments}")
                        function_args = {}
                    
                    # Execute the function
                    if function_name == "fetch_dune_metrics":
                        tool_result = await self._tool_fetch_dune_metrics(**function_args)
                    elif function_name == "fetch_gecko_competitors":
                        tool_result = await self._tool_fetch_gecko_competitors(**function_args)
                    else:
                        tool_result = {"error": f"Unknown function: {function_name}"}
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result),
                    })
                
                iteration += 1
                continue  # Continue the loop to get the final response
            
            # No tool calls, we have the final response
            break
        
        content = (message.content or "").strip()
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
    
    async def _tool_fetch_dune_metrics(
        self,
        pool_address: str,
        blockchain: str,
        dex: str,
        main_token_symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool function for AI to fetch Dune metrics."""
        try:
            metrics = await self.dune_service.fetch_metrics_for_pool(
                pool_address=pool_address,
                blockchain=blockchain,
                dex=dex,
                main_token_symbol=main_token_symbol,
            )
            # Format the metrics for the AI
            formatted = self._format_dune_metrics(metrics)
            return {
                "success": True,
                "pool_address": pool_address,
                "metrics": formatted,
            }
        except Exception as e:
            logger.warning(f"Error in tool_fetch_dune_metrics: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _tool_fetch_gecko_competitors(
        self,
        network: str,
        token_address: str,
        top_n: int = 3,
    ) -> Dict[str, Any]:
        """Tool function for AI to fetch competitor pools from GeckoTerminal."""
        try:
            # The benchmarker searches for pools containing token_b paired with any token
            # We'll use token_address as token_b and pass empty token_a
            competitors = await self.dex_benchmarker.fetch_competitors(
                network=network,
                token_a="",  # Not used when searching by token_b
                token_b=token_address,
                top_n=top_n,
            )
            return {
                "success": True,
                "network": network,
                "token_address": token_address,
                "competitors": competitors,
            }
        except Exception as e:
            logger.warning(f"Error in tool_fetch_gecko_competitors: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def _load_metrics_docs(self) -> str:
        """Load the metrics documentation that explains all Dune metrics."""
        doc_file = os.path.join(self.docs_dir, "metrics.md")
        if os.path.exists(doc_file):
            try:
                with open(doc_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to load metrics docs: {e}")
        return ""

