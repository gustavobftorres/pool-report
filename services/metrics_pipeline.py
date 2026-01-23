"""
Metrics pipeline orchestrator for analyzing pools with competitors.
Fetches metrics from Dune Analytics for input pool and competitor pools.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from services.balancer_api import BalancerAPI
from services.dex_benchmarker import DEXBenchmarker
from services.dune_metrics import DuneMetricsService, METRIC_GROUP_NAMES
from config import settings

logger = logging.getLogger(__name__)


class MetricsPipeline:
    """Orchestrates the full metrics pipeline for pool analysis."""

    def __init__(self) -> None:
        """Initialize pipeline services."""
        self.balancer_api = BalancerAPI()
        self.dex_benchmarker = DEXBenchmarker()
        self.dune_service = DuneMetricsService()

    def _normalize_network(self, pool_data: Dict[str, Any]) -> str:
        """
        Map pool data or settings to a GeckoTerminal network slug.
        
        Args:
            pool_data: Pool data from Balancer API
            
        Returns:
            Network slug for GeckoTerminal (e.g., "eth", "arbitrum")
        """
        raw = (
            pool_data.get("_blockchain")
            or settings.blockchain_name
            or settings.default_chain
            or "ethereum"
        ).lower()
        
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

    def _extract_tokens_for_benchmark(self, pool_data: Dict[str, Any]) -> List[str]:
        """
        Extract benchmark token addresses (prefer 2 core ERC-20 tokens, skip BPT/LP-like tokens).
        This prevents accidentally choosing internal/BPT-like tokens that won't resolve on GeckoTerminal.
        
        Args:
            pool_data: Pool data from Balancer API
            
        Returns:
            List of token addresses (at most 2)
        """
        tokens = (
            pool_data.get("allTokens")
            or pool_data.get("displayTokens")
            or pool_data.get("tokens")
            or []
        )
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

    def _extract_main_token_symbol(self, pool_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the main token symbol from pool data.
        Prefers the token with the highest weight, or the first non-BPT token.
        
        Args:
            pool_data: Pool data from Balancer API
            
        Returns:
            Main token symbol or None if not found
        """
        tokens = (
            pool_data.get("allTokens")
            or pool_data.get("displayTokens")
            or pool_data.get("tokens")
            or []
        )
        
        if not tokens:
            return None
        
        # Try to find token with highest weight first
        tokens_with_weights = []
        for t in tokens:
            symbol = (t.get("symbol") or "").upper()
            # Skip BPT/LP tokens
            if "BPT" in symbol or symbol in {"BPT", "BALANCER", "POOL"}:
                continue
            
            weight = t.get("weight")
            if weight is not None:
                try:
                    weight_float = float(weight)
                    tokens_with_weights.append((weight_float, t.get("symbol")))
                except (ValueError, TypeError):
                    pass
        
        # Sort by weight descending and return the symbol of the highest weight token
        if tokens_with_weights:
            tokens_with_weights.sort(key=lambda x: x[0], reverse=True)
            return tokens_with_weights[0][1]
        
        # Fallback: return first non-BPT token symbol
        for t in tokens:
            symbol = t.get("symbol")
            if symbol and "BPT" not in symbol.upper() and symbol.upper() not in {"BPT", "BALANCER", "POOL"}:
                return symbol
        
        return None

    def _identify_pool_dex(self, pool_data: Dict[str, Any]) -> str:
        """
        Identify the DEX type for a pool.
        For Balancer pools, this will be "Balancer".
        
        Args:
            pool_data: Pool data from Balancer API
            
        Returns:
            Normalized DEX name
        """
        # If it's from Balancer API, it's a Balancer pool
        # In the future, this could check pool_data for other indicators
        return "Balancer"

    def _get_blockchain_for_dune(self, pool_data: Dict[str, Any]) -> str:
        """
        Get blockchain name for Dune queries.
        
        Args:
            pool_data: Pool data from API
            
        Returns:
            Blockchain name for Dune (e.g., "ethereum")
        """
        blockchain = (
            pool_data.get("_blockchain")
            or settings.blockchain_name
            or "ethereum"
        ).lower()
        
        # Normalize to Dune's expected format
        blockchain_map = {
            "mainnet": "ethereum",
            "eth": "ethereum",
            "arbitrum": "arbitrum",
            "polygon": "polygon",
            "optimism": "optimism",
            "base": "base",
        }
        return blockchain_map.get(blockchain, blockchain)

    async def analyze_pool_with_competitors(
        self, pool_address: str
    ) -> Dict[str, Any]:
        """
        Main pipeline method: analyze a pool and its competitors.
        
        Args:
            pool_address: Pool address to analyze
            
        Returns:
            Dictionary with metrics for input pool and competitors
        """
        print(f"\n{'='*60}")
        print(f"Starting Metrics Pipeline Analysis")
        print(f"{'='*60}")
        print(f"Input Pool Address: {pool_address}\n")

        results = {
            "input_pool": None,
            "competitors": [],
        }

        # Step 1: Get pool data from Balancer API
        print("Step 1: Fetching input pool data from Balancer API...")
        try:
            pool_data = await self.balancer_api.get_current_pool_data(pool_address)
            print(f"✅ Found pool: {pool_data.get('name', 'Unknown')}")
        except Exception as e:
            print(f"❌ Error fetching pool data: {e}")
            return results

        # Step 2: Identify input pool DEX type
        print("\nStep 2: Identifying input pool DEX type...")
        input_dex = self._identify_pool_dex(pool_data)
        print(f"✅ Input pool DEX: {input_dex}")

        # Step 3: Extract token addresses for competitor search
        print("\nStep 3: Extracting token addresses for competitor search...")
        blockchain = self._get_blockchain_for_dune(pool_data)
        main_token_symbol = self._extract_main_token_symbol(pool_data)
        if main_token_symbol:
            print(f"   Main token symbol: {main_token_symbol}")
        
        tokens = self._extract_tokens_for_benchmark(pool_data)
        if len(tokens) < 2:
            print(
                f"⚠️  Could not extract 2 tokens from pool data. Found: {len(tokens)}"
            )
            print("   Skipping competitor analysis, fetching input pool metrics only...")
            # Still fetch input pool metrics even if no competitors
            try:
                input_metrics = await self.dune_service.fetch_metrics_for_pool(
                    pool_address=pool_address,
                    blockchain=blockchain,
                    dex=input_dex,
                    main_token_symbol=main_token_symbol,
                )
                results["input_pool"] = {
                    "pool_address": pool_address,
                    "pool_name": pool_data.get("name", "Unknown"),
                    "dex": input_dex,
                    "blockchain": blockchain,
                    "metrics": input_metrics,
                }
                print(f"✅ Fetched {len(input_metrics)} metric groups for input pool")
            except Exception as e:
                print(f"❌ Error fetching input pool metrics: {e}")
                logger.error(f"Error fetching input pool metrics: {e}", exc_info=e)
            return results
        
        token_a, token_b = tokens[0], tokens[1]
        print(f"✅ Token A: {token_a}")
        print(f"✅ Token B: {token_b}")

        # Step 4: Fetch competitors via GeckoTerminal
        print("\nStep 4: Fetching competitor pools from GeckoTerminal...")
        network = self._normalize_network(pool_data)
        competitors = []
        try:
            competitor_data = await self.dex_benchmarker.fetch_competitors(
                network=network,
                token_a=token_a,
                token_b=token_b,
                top_n=3,
                exclude_pool_address=pool_address,  # Exclude the input pool
            )
            competitors = competitor_data.get("competitors", [])
            print(f"✅ Found {len(competitors)} competitor pools")
        except Exception as e:
            print(f"❌ Error fetching competitors: {e}")
            logger.error(f"Error fetching competitors: {e}", exc_info=e)
            # Still fetch input pool metrics even if competitor fetch fails
            competitors = []

        # Step 5: Prepare all pools for parallel metric fetching
        print("\nStep 5: Preparing pools for parallel metric fetching...")
        
        # Prepare input pool task
        input_pool_task = {
            "type": "input",
            "pool_address": pool_address,
            "pool_name": pool_data.get("name", "Unknown"),
            "dex": input_dex,
            "blockchain": blockchain,
            "main_token_symbol": main_token_symbol,
        }
        
        # Prepare competitor pool tasks
        competitor_tasks = []
        for i, competitor in enumerate(competitors, 1):
            pool_name = competitor.get("name", "Unknown")
            dex_normalized = competitor.get("dex_normalized")
            pool_addr = competitor.get("pool_address")

            if not pool_addr:
                print(f"⚠️  Competitor {i}: {pool_name} - No pool address found, skipping")
                continue

            if not dex_normalized:
                print(
                    f"⚠️  Competitor {i}: {pool_name} - Unknown DEX type '{competitor.get('dex')}', skipping"
                )
                continue

            # Extract main token symbol from competitor pool tokens
            competitor_main_token = None
            competitor_tokens = competitor.get("tokens", [])
            if competitor_tokens:
                competitor_main_token = competitor_tokens[0].get("symbol")
            
            # Fallback to input pool's main token if competitor token not available
            if not competitor_main_token:
                competitor_main_token = main_token_symbol

            competitor_tasks.append({
                "type": "competitor",
                "pool_address": pool_addr,
                "pool_name": pool_name,
                "dex": dex_normalized,
                "blockchain": blockchain,
                "main_token_symbol": competitor_main_token,
                "dex_original": competitor.get("dex"),  # Keep original for reference
            })
            print(f"  ✅ Prepared: {pool_name} ({dex_normalized}) - {pool_addr}")

        # Step 6: Fetch metrics for all pools in parallel
        total_pools = 1 + len(competitor_tasks)
        print(f"\nStep 6: Fetching metrics for {total_pools} pools in parallel...")
        print(f"   Input pool: {input_pool_task['pool_name']} ({input_dex})")
        if competitor_tasks:
            print(f"   Competitors: {len(competitor_tasks)} pools")
            for task in competitor_tasks:
                print(f"     - {task['pool_name']} ({task['dex']})")
        
        async def fetch_pool_metrics(task):
            """Helper to fetch metrics for a single pool."""
            try:
                metrics = await self.dune_service.fetch_metrics_for_pool(
                    pool_address=task["pool_address"],
                    blockchain=task["blockchain"],
                    dex=task["dex"],
                    main_token_symbol=task["main_token_symbol"],
                )
                return {
                    "success": True,
                    "task": task,
                    "metrics": metrics,
                }
            except Exception as e:
                logger.error(
                    f"Error fetching metrics for {task['pool_name']}: {e}",
                    exc_info=e,
                )
                return {
                    "success": False,
                    "task": task,
                    "error": str(e),
                }
        
        # Fetch all pools in parallel using asyncio.gather
        all_tasks = [input_pool_task] + competitor_tasks
        metric_results = await asyncio.gather(
            *[fetch_pool_metrics(task) for task in all_tasks],
            return_exceptions=True
        )
        
        # Process results
        for result in metric_results:
            if isinstance(result, Exception):
                logger.error(f"Unexpected error in parallel fetch: {result}", exc_info=result)
                continue
            
            if not result.get("success"):
                task = result["task"]
                print(f"❌ Error fetching metrics for {task['pool_name']}: {result.get('error')}")
                continue
            
            task = result["task"]
            metrics = result["metrics"]
            
            if task["type"] == "input":
                results["input_pool"] = {
                    "pool_address": task["pool_address"],
                    "pool_name": task["pool_name"],
                    "dex": task["dex"],
                    "blockchain": task["blockchain"],
                    "metrics": metrics,
                }
                print(f"✅ Fetched {len(metrics)} metric groups for input pool: {task['pool_name']}")
            else:
                results["competitors"].append({
                    "pool_address": task["pool_address"],
                    "pool_name": task["pool_name"],
                    "dex": task.get("dex_original"),  # Original DEX name
                    "dex_normalized": task["dex"],
                    "blockchain": task["blockchain"],
                    "metrics": metrics,
                })
                print(f"✅ Fetched {len(metrics)} metric groups for competitor: {task['pool_name']} ({task['dex']})")

        print(f"\n{'='*60}")
        print(f"Pipeline Analysis Complete")
        print(f"{'='*60}\n")

        return results

    def print_metrics(self, results: Dict[str, Any]) -> None:
        """
        Print all metrics in a structured format.
        
        Args:
            results: Results dictionary from analyze_pool_with_competitors
        """
        # Print input pool metrics
        if results.get("input_pool"):
            input_pool = results["input_pool"]
            print("\n" + "=" * 80)
            print("POOL ANALYSIS: INPUT POOL")
            print("=" * 80)
            print(f"Pool: {input_pool['pool_name']} ({input_pool['dex']})")
            print(f"Address: {input_pool['pool_address']}")
            print(f"Network: {input_pool['blockchain']}")
            print()

            metrics = input_pool.get("metrics", {})
            for metric_group, group_name in METRIC_GROUP_NAMES.items():
                print(f"--- {group_name} ---")
                if metric_group in metrics:
                    metric_data = metrics[metric_group]
                    if "error" in metric_data:
                        print(f"  Error: {metric_data['error']}")
                    else:
                        rows = metric_data.get("rows", [])
                        if rows:
                            # Print first few rows as sample
                            for row in rows[:3]:
                                print(f"  {row}")
                            if len(rows) > 3:
                                print(f"  ... ({len(rows) - 3} more rows)")
                        else:
                            print("  No data returned")
                else:
                    print("  No data available")
                print()

        # Print competitor pool metrics
        competitors = results.get("competitors", [])
        if competitors:
            print("\n" + "=" * 80)
            print("COMPETITOR POOL ANALYSIS")
            print("=" * 80)

            for i, competitor in enumerate(competitors, 1):
                print(f"\n--- Competitor {i}/{len(competitors)} ---")
                print(f"Pool: {competitor['pool_name']} ({competitor.get('dex', 'Unknown')})")
                print(f"Address: {competitor['pool_address']}")
                print(f"Network: {competitor['blockchain']}")
                print()

                metrics = competitor.get("metrics", {})
                for metric_group, group_name in METRIC_GROUP_NAMES.items():
                    print(f"  --- {group_name} ---")
                    if metric_group in metrics:
                        metric_data = metrics[metric_group]
                        if "error" in metric_data:
                            print(f"    Error: {metric_data['error']}")
                        else:
                            rows = metric_data.get("rows", [])
                            if rows:
                                # Print first few rows as sample
                                for row in rows[:3]:
                                    print(f"    {row}")
                                if len(rows) > 3:
                                    print(f"    ... ({len(rows) - 3} more rows)")
                            else:
                                print("    No data returned")
                    else:
                        print("    No data available")
                    print()

        else:
            print("\nNo competitor pools analyzed.")
