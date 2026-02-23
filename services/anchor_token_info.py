"""
Service to retrieve anchor token pool information.
Uses GeckoTerminal API only - all pools have pool_address, volume, fees, liquidity, dex.
"""
import asyncio
import pandas as pd
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from services.gecko_pool import fetch_pools_for_token_gecko_only

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
        pass

    async def get_token_data(self, token_address: str, blockchain: str = "ethereum", debug: bool = False) -> pd.DataFrame:
        """
        Fetch all DEX pools for a token from GeckoTerminal (GeckoTerminal-only, no DefiLlama).
        Every pool has pool_address, volume, fees, liquidity, dex - no empty rows.

        Args:
            token_address: The address of the anchor token.
            blockchain: The blockchain network (default: ethereum).
            debug: If True, exports the resulting DataFrame to Google Spreadsheet.

        Returns:
            Pandas DataFrame with pool data.
        """
        token_address = token_address.lower()
        print(f"🔍 Fetching pool data for anchor token: {token_address} on {blockchain}")
        print(f"  → Fetching from GeckoTerminal (tokens/pools)...")
        try:
            pools = await asyncio.to_thread(
                fetch_pools_for_token_gecko_only, blockchain, token_address
            )
            if not pools:
                print(f"⚠️ No pools found for token {token_address}")
                return pd.DataFrame()
            print(f"  ✅ Found {len(pools)} pools (all with pool_address).")
            df_result = pd.DataFrame(pools)
            if debug and not df_result.empty:
                try:
                    from services.spreadsheet_service import export_dataframe_to_sheet
                    export_dataframe_to_sheet(df_result)
                    print("📝 Anchor token info exported to Google Spreadsheet")
                except Exception as e:
                    logger.error(f"Failed to export to spreadsheet: {e}")
                    raise
            return df_result
        except Exception as e:
            logger.error(f"Error fetching pools: {e}")
            return pd.DataFrame()

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
    
    def get_summary_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate human-readable summary from the DataFrame."""
        if df.empty:
            return {"status": "No data available"}
            
        stats = {
            "total_markets": len(df),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if "volume" in df.columns:
            stats["cumulative_volume"] = df["volume"].sum()
        elif "total_volume_usd" in df.columns:
            stats["cumulative_volume"] = df["total_volume_usd"].sum()

        return stats
