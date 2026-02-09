"""
Dune Analytics service for fetching pool metrics.
Handles query execution and result retrieval for all metric groups.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from dune_client.client import DuneClient
from dune_client.query import QueryBase
from dune_client.types import QueryParameter

from config import settings

logger = logging.getLogger(__name__)


# Query ID mapping: 8 metric groups × 5 DEXs = 40 queries
DUNE_QUERIES = {
    "demand_usage": {
        "UniSwap": 6583146,
        "Fluid": 6583133,
        "Curve": 6583117,
        "Balancer": 6576923,
        "PancakeSwap": 6583446,
    },
    "liquidity_depth": {
        "UniSwap": 6587972,
        "Fluid": 6587953,
        "Curve": 6587962,
        "Balancer": 6587861,
        "PancakeSwap": 6587974,
    },
    "fee_monetization": {
        "UniSwap": 6582703,
        "Fluid": 6582671,
        "Curve": 6583075,
        "Balancer": 6582526,
        "PancakeSwap": 6582732,
    },
    "capital_efficiency": {
        "UniSwap": 6587988,
        "Fluid": 6587983,
        "Curve": 6587986,
        "Balancer": 6587887,
        "PancakeSwap": 6587990,
    },
    "lp_outcome": {
        "UniSwap": 6582905,
        "Fluid": 6582888,
        "Curve": 6582917,
        "Balancer": 6587905,
        "PancakeSwap": 6582923,
    },
    "behavioral_market_power": {
        "UniSwap": 6583000,
        "Fluid": 6582995,
        "Curve": 6583007,
        "Balancer": 6582949,
        "PancakeSwap": 6583018,
    },
    "comparative_positioning": {
        "UniSwap": 6583057,
        "Fluid": 6583050,
        "Curve": 6583063,
        "Balancer": 6583035,
        "PancakeSwap": 6583066,
    },
    "volume_depth_unit": {
        "UniSwap": 6588014,
        "Fluid": 6588001,
        "Curve": 6588009,
        "Balancer": 6587900,
        "PancakeSwap": 6588023,
    },
}

# Metric group display names
METRIC_GROUP_NAMES = {
    "demand_usage": "Demand / Usage Metrics",
    "liquidity_depth": "Liquidity & Depth Metrics",
    "fee_monetization": "Fee & Monetization Metrics",
    "capital_efficiency": "Capital Efficiency Metrics",
    "lp_outcome": "LP Outcome Metrics",
    "behavioral_market_power": "Behavioral & Market Power Metrics",
    "comparative_positioning": "Comparative Positioning Metrics",
    "volume_depth_unit": "Volume Depth Unit Metrics",
}


class DuneMetricsService:
    """Service for fetching pool metrics from Dune Analytics."""

    def __init__(self) -> None:
        """Initialize Dune client with API key from settings."""
        api_key = settings.dune_api_key
        if not api_key:
            raise ValueError(
                "Dune API key not configured. Set DUNE_API_KEY in environment or .env file."
            )
        # Verify API key is not empty
        if not api_key or len(api_key.strip()) == 0:
            raise ValueError("Dune API key is empty. Check your .env file.")
        
        # Use positional argument like in working dune-test.py example
        self.client = DuneClient(api_key)
        self.performance = settings.dune_query_performance
        self.timeout = settings.dune_query_timeout
        
        # Log API key status (first 4 chars only for security)
        logger.info(f"Dune client initialized with API key: {api_key[:4]}...")

    def get_query_id(self, metric_group: str, dex: str) -> Optional[int]:
        """
        Get query ID for a specific metric group and DEX.

        Args:
            metric_group: One of the 7 metric groups
            dex: DEX name (UniSwap, Fluid, Curve, Balancer, PancakeSwap)

        Returns:
            Query ID or None if not found
        """
        return DUNE_QUERIES.get(metric_group, {}).get(dex)

    async def fetch_metrics_for_pool(
        self,
        pool_address: str,
        blockchain: str,
        dex: str,
        main_token_symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch all metric groups for a pool from Dune.

        Args:
            pool_address: Pool address (0x...)
            blockchain: Blockchain name (e.g., "ethereum")
            dex: DEX name (must match keys in DUNE_QUERIES)
            main_token_symbol: Main token symbol (required for comparative_positioning queries)

        Returns:
            Dictionary with metric groups as keys and query results as values
        """
        results = {}
        metric_groups = list(DUNE_QUERIES.keys())

        # Execute queries with small delays to avoid rate limiting
        # IMPORTANT: Only execute queries for the specified DEX
        # Each competitor pool will only query its own DEX (e.g., Fluid pool → only Fluid queries)
        logger.info(f"Fetching metrics for {dex} pool {pool_address} - will only query {dex} queries")
        tasks = []
        for idx, metric_group in enumerate(metric_groups):
            query_id = self.get_query_id(metric_group, dex)
            if query_id:
                logger.debug(f"  Adding query for {metric_group} (DEX: {dex}, Query ID: {query_id})")
                # Add small delay between query submissions to avoid rate limiting
                # Delay increases slightly for each query
                delay = idx * 0.1  # 0.1s, 0.2s, 0.3s, etc.
                
                async def _delayed_query(delay_time, mg, qid):
                    if delay_time > 0:
                        await asyncio.sleep(delay_time)
                    return await self._execute_query(
                        query_id=qid,
                        pool_address=pool_address,
                        blockchain=blockchain,
                        metric_group=mg,
                        main_token_symbol=main_token_symbol if mg == "comparative_positioning" else None,
                    )
                
                tasks.append(_delayed_query(delay, metric_group, query_id))
            else:
                logger.warning(
                    f"No query found for metric_group={metric_group}, dex={dex}"
                )
                results[metric_group] = {
                    "error": f"No query mapping for {metric_group} / {dex}",
                    "rows": [],
                }

        # Wait for all queries to complete (return exceptions instead of raising)
        query_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Organize results by metric group
        for i, metric_group in enumerate(metric_groups):
            query_id = self.get_query_id(metric_group, dex)
            if query_id:
                result = query_results[i]
                if isinstance(result, Exception):
                    # Log error but continue with other queries
                    error_msg = str(result)
                    logger.warning(
                        f"Error fetching {metric_group} (query {query_id}) for {dex}: {error_msg}"
                    )
                    results[metric_group] = {
                        "error": error_msg,
                        "rows": [],
                        "query_id": query_id,
                    }
                else:
                    results[metric_group] = result

        return results

    async def _execute_query(
        self,
        query_id: int,
        pool_address: str,
        blockchain: str,
        metric_group: str,
        main_token_symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single Dune query and wait for results.

        Args:
            query_id: Dune query ID
            pool_address: Pool address parameter
            blockchain: Blockchain parameter
            metric_group: Metric group name (for logging)
            main_token_symbol: Main token symbol (required for comparative_positioning queries)

        Returns:
            Dictionary with query results
        """
        try:
            logger.info(
                f"Executing Dune query {query_id} ({metric_group}) for pool {pool_address}"
            )

            # Build params
            params = {
                "blockchain": blockchain,
            }
            
            # Standard queries use pool_address, anchor_volume uses token_address
            if metric_group == "anchor_volume":
                params["token_address"] = pool_address.lower()
                if main_token_symbol:
                    params["token_symbol_placeholder"] = main_token_symbol
            else:
                params["pool_address"] = pool_address.lower()
                
            # comparative_positioning needs main_token_symbol
            if metric_group == "comparative_positioning" and main_token_symbol:
                params["main_token_symbol"] = main_token_symbol

            # Dune client is synchronous, so run in thread pool to avoid blocking
            def _run_query():
                # Use QueryBase and run_query() as shown in working dune-test.py example
                # Convert params dict to QueryParameter list using text_type
                query_params = [
                    QueryParameter.text_type(key, str(value))
                    for key, value in params.items()
                ]
                
                # Log parameters for debugging (especially for failing queries)
                if metric_group == "liquidity_depth":
                    logger.info(
                        f"DEBUG liquidity_depth query {query_id}: params={params}, "
                        f"query_params count={len(query_params)}"
                    )
                
                # Create QueryBase object with query_id and params
                query = QueryBase(
                    query_id=query_id,
                    params=query_params
                )
                
                # Use run_query which executes query and waits for results
                # For liquidity_depth, add retry logic since it sometimes fails in parallel execution
                max_retries = 3 if metric_group == "liquidity_depth" else 1
                retry_delay = 0.5
                
                for attempt in range(max_retries):
                    try:
                        results = self.client.run_query(query)
                        
                        # Extract rows from results.result.rows (as per working example)
                        rows = results.result.rows if hasattr(results, 'result') and hasattr(results.result, 'rows') else []
                        execution_id = getattr(results, 'execution_id', None) if hasattr(results, 'execution_id') else None
                        
                        return {
                            'rows': rows,
                            'execution_id': execution_id
                        }
                    except Exception as e:
                        # If this is the last attempt, raise the error
                        if attempt == max_retries - 1:
                            raise
                        # Otherwise, wait and retry (only for xliquidity_depth)
                        if metric_group == "liquidity_depth":
                            logger.warning(
                                f"liquidity_depth query {query_id} failed on attempt {attempt + 1}, retrying in {retry_delay}s..."
                            )
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            raise
                
                # This should never be reached, but just in case
                raise Exception("Failed after all retries")

            # Run synchronous Dune client call in thread pool
            result = await asyncio.to_thread(_run_query)

            # Extract rows and execution_id from result dict
            rows = result.get('rows', [])
            execution_id = result.get('execution_id', None)

            logger.info(
                f"Query {query_id} completed: {len(rows)} rows returned"
            )
            return {
                "rows": rows,
                "execution_id": execution_id,
                "query_id": query_id,
            }

        except Exception as e:
            # Log error but don't raise - let the caller handle it via return_exceptions=True
            logger.warning(
                f"Error executing Dune query {query_id} ({metric_group}): {e}"
            )
            # Return error info instead of raising
            return {
                "rows": [],
                "execution_id": None,
                "query_id": query_id,
                "error": str(e),
            }
