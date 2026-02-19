"""
Service to retrieve anchor token lending market and volume information.
Combines data from DefiLlama (lending) and Dune Analytics (volume).
"""
import asyncio
import httpx
import pandas as pd
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from services.balancer_api import BalancerAPI
from services.dune_metrics import DuneMetricsService
from config import settings

logger = logging.getLogger(__name__)

class AnchorTokenInfo:
    """
    Class to retrieve and aggregate anchor token lending market and volume information.
    
    Common Token Symbols by Address (Ethereum mainnet):
    """
    
    # Common token address -> symbol mapping (lowercase addresses)
    TOKEN_SYMBOLS = {
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH",
        "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0": "wstETH",
        "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
        "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
        "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": "WBTC",
        "0xae78736cd615f374d3085123a210448e74fc6393": "rETH",
        "0xbe9895146f7af43049ca1c1ae358b0541ea49704": "cbETH",
        "0xd11c452fc99cf405034ee446803b6f6c1f6d5ed8": "tETH",  # Treehouse ETH
    }
    
    """
    SQL Template for Dune Analytics Volume Query:
    --------------------------------------------
    -- Parameters: {{token_address}}, {{blockchain}}, {{token_symbol_placeholder}}
    -- This query aggregates Balancer swap volume by chain, version, and token pair.
    -- IMPORTANT: In Dune UI, set blockchain as TEXT type (use 'ethereum' not ethereum)
    
    WITH prices AS (
        SELECT 
            date_trunc('day', minute) as day,
            contract_address,
            AVG(price) as price_usd
        FROM prices.usd
        WHERE contract_address = from_hex({{token_address}})
          AND minute > now() - interval '30 days'
        GROUP BY 1, 2
    ),
    
    swaps AS (
        SELECT 
            s.blockchain,
            COALESCE(s.version, 'unknown') as project_version,
            CASE 
                WHEN s.token_bought_address = from_hex({{token_address}}) THEN s.token_sold_symbol
                WHEN s.token_sold_address = from_hex({{token_address}}) THEN s.token_bought_symbol
                ELSE 'UNKNOWN'
            END as pair_token_symbol,
            CASE 
                WHEN s.token_bought_address = from_hex({{token_address}}) THEN s.token_bought_amount
                WHEN s.token_sold_address = from_hex({{token_address}}) THEN s.token_sold_amount
                ELSE 0
            END as token_amount,
            s.block_time,
            s.token_bought_address,
            s.token_sold_address
        FROM dex.trades s
        WHERE s.project = 'balancer'
          AND (s.token_bought_address = from_hex({{token_address}}) 
               OR s.token_sold_address = from_hex({{token_address}}))
          AND s.blockchain = '{{blockchain}}'
          AND s.block_time > now() - interval '30 days'
    )

    SELECT 
        s.blockchain,
        s.project_version,
        s.pair_token_symbol || '-' || '{{token_symbol_placeholder}}' as token_pair,
        SUM(s.token_amount * COALESCE(p.price_usd, 0)) as total_volume_usd,
        COUNT(*) as swap_count
    FROM swaps s
    LEFT JOIN prices p ON date_trunc('day', s.block_time) = p.day 
       AND p.contract_address = from_hex({{token_address}})
    GROUP BY 1, 2, 3
    ORDER BY total_volume_usd DESC;
    
    Expected Output Schema:
    - blockchain (text): The blockchain network (e.g., 'ethereum', 'arbitrum')
    - project_version (text): Balancer version (e.g., '2', '3', 'unknown')
    - token_pair (text): Trading pair name (e.g., 'USDC-WETH', 'DAI-WETH')
    - total_volume_usd (double): Total USD volume for this pair over 30 days
    - swap_count (bigint): Number of swaps involving this token
    """

    def __init__(self) -> None:
        self.balancer_api = BalancerAPI()
        try:
            self.dune_service = DuneMetricsService()
            self.dune_available = True
        except Exception as e:
            logger.warning(f"Dune service initialization failed: {e}. Volume data will be limited.")
            self.dune_available = False
            
        self.lllama_yields_url = "https://yields.llama.fi/pools"

    async def get_token_data(self, token_address: str, blockchain: str = "ethereum", debug: bool = False) -> pd.DataFrame:
        """
        Orchestrator to fetch lending and volume data for a specific token.
        
        Args:
            token_address: The address of the anchor token.
            blockchain: The blockchain network (default: ethereum).
            debug: If True, exports the resulting DataFrame to Google Spreadsheet.
            
        Returns:
            Pandas DataFrame with aggregated market and performance data.
        """
        token_address = token_address.lower()
        print(f"🔍 Fetching comprehensive data for anchor token: {token_address} on {blockchain}")
        
        # 1. Fetch data in parallel
        tasks = [
            self._get_lending_markets(token_address),
            self._get_historical_volume(token_address, blockchain)
        ]
        
        lending_data, volume_data = await asyncio.gather(*tasks)
        
        # 2. Merge and Normalize Data
        df_lending = pd.DataFrame(lending_data)
        df_volume = pd.DataFrame(volume_data)
        
        if df_lending.empty and df_volume.empty:
            print(f"⚠️ No data found for token {token_address}")
            return pd.DataFrame()

        # 3. Create a unified view
        if df_volume.empty:
            df_result = df_lending
        elif df_lending.empty:
            df_result = df_volume
        else:
            # Add best lending market info to volume rows
            df_result = df_volume.copy()
            best_market = df_lending.iloc[0].to_dict()
            for col, val in best_market.items():
                if col not in df_result.columns:
                    if isinstance(val, (list, dict)):
                        val = str(val)
                    df_result[f"best_market_{col}"] = val
        
        if debug and not df_result.empty:
            try:
                from services.spreadsheet_service import export_dataframe_to_sheet
                export_dataframe_to_sheet(df_result)
                print("📝 Anchor token info exported to Google Spreadsheet")
            except Exception as e:
                logger.error(f"Failed to export to spreadsheet: {e}")
                raise

        return df_result

    async def _get_lending_markets(self, token_address: str) -> List[Dict[str, Any]]:
        """Fetch lending market yields from DefiLlama."""
        if token_address:
            token_address = token_address.lower()
        print(f"  → Fetching lending markets from DefiLlama...")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.lllama_yields_url)
                if response.status_code != 200:
                    return []
                
                data = response.json().get('data', [])
                # Filter pools where this token is the underlying
                # DefiLlama uses addresses in its internal format, sometimes checksummed or lowercase
                token_pools = [
                    {
                        "protocol": p.get('project'),
                        "chain": p.get('chain'),
                        "symbol": p.get('symbol'),
                        "apy": p.get('apy'),
                        "tvl_usd": p.get('tvlUsd'),
                        "reward_tokens": p.get('rewardTokens'),
                        "pool_address": _extract_pool_address(p.get('pool'))
                    }
                    for p in data 
                    if p.get('underlyingTokens') and token_address in [t.lower() if t else '' for t in p.get('underlyingTokens', [])]
                ]
                
                # Sort by APY descending
                token_pools.sort(key=lambda x: x['apy'] or 0, reverse=True)
                print(f"  ✅ Found {len(token_pools)} lending markets.")
                return token_pools
        except Exception as e:
            logger.error(f"Error fetching lending markets: {e}")
            return []

    def _resolve_token_symbol(self, token_address: str) -> str:
        """
        Resolve token symbol from address.
        First tries the known token mapping, then defaults to 'TOKEN'.
        
        Args:
            token_address: Token address (case-insensitive)
            
        Returns:
            Token symbol string
        """
        token_address = token_address.lower()
        return self.TOKEN_SYMBOLS.get(token_address, "TOKEN")
    
    async def _get_historical_volume(self, token_address: str, blockchain: str) -> List[Dict[str, Any]]:
        """
        Fetch historical volume from Dune Analytics.
        Note: Requires a specific query ID configured in settings.
        """
        if not self.dune_available:
            return []
            
        # Try to find a specific query for anchor token volume in settings/mapping
        query_id = getattr(settings, 'dune_anchor_volume_query_id', None)
        
        if not query_id:
            print("  ℹ️ No Dune Query ID configured for Anchor Volume. Skipping Dune fetch.")
            return []

        # Resolve token symbol from address
        token_symbol = self._resolve_token_symbol(token_address)

        print(f"  → Fetching historical volume from Dune (Query {query_id})...")
        try: 
            # Reusing the logic from DuneMetricsService
            result = await self.dune_service._execute_query(
                query_id=query_id,
                pool_address=token_address, 
                blockchain=blockchain,
                metric_group="anchor_volume",
                main_token_symbol=token_symbol # We'll reuse main_token_symbol param for the placeholder
            )
            rows = result.get('rows', [])
            print(f"  ✅ Fetched {len(rows)} volume records from Dune.")
            return rows
        except Exception as e:
            logger.error(f"Error fetching Dune volume: {e}")
            return []

    def get_summary_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate human-readable summary from the DataFrame."""
        if df.empty:
            return {"status": "No data available"}
            
        stats = {
            "total_markets": len(df),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if "apy" in df.columns:
            stats["avg_apy"] = df["apy"].mean()
            stats["max_apy"] = df["apy"].max()
            
        if "total_volume_usd" in df.columns:
            stats["cumulative_volume"] = df["total_volume_usd"].sum()
            
        return stats
