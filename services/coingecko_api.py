"""
CoinGecko API integration for historical token prices.

Free API endpoint: https://api.coingecko.com/api/v3
Rate limit: 50 calls/minute (free tier)
"""
from __future__ import annotations

import asyncio
import httpx
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from functools import lru_cache

logger = logging.getLogger(__name__)


class CoinGeckoAPI:
    """Fetch historical token prices from CoinGecko."""
    
    def __init__(self):
        """Initialize CoinGecko client."""
        self.base_url = "https://api.coingecko.com/api/v3"
        self.timeout = 30.0
        self.cache: Dict[str, Any] = {}  # Simple in-memory cache
        
    async def get_token_price_history(
        self,
        token_address: str,
        days: int = 30,
        vs_currency: str = "usd",
    ) -> List[Dict[str, float]]:
        """
        Get historical prices for a token.
        
        Args:
            token_address: Ethereum token address (0x...)
            days: Number of days of history (max 90 for free tier)
            vs_currency: Currency to price against (default: usd)
            
        Returns:
            List of price points: [{"timestamp": 1234567890, "price": 1.23}, ...]
            
        Example:
            >>> api = CoinGeckoAPI()
            >>> prices = await api.get_token_price_history(
            ...     "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
            ...     days=30
            ... )
            >>> print(f"Price 30 days ago: ${prices[0]['price']:.4f}")
        """
        # Check cache first (24h TTL)
        cache_key = f"{token_address}_{days}_{vs_currency}"
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if (datetime.now(timezone.utc) - cached_time).total_seconds() < 86400:
                logger.info(f"Using cached price data for {token_address[:8]}...")
                return cached_data
        
        # Normalize address
        token_address = token_address.lower()
        
        # CoinGecko endpoint: /coins/ethereum/contract/{address}/market_chart
        url = f"{self.base_url}/coins/ethereum/contract/{token_address}/market_chart"
        params = {
            "vs_currency": vs_currency,
            "days": days,
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Parse response: {"prices": [[timestamp_ms, price], ...]}
            prices_raw = data.get("prices", [])
            
            prices = [
                {
                    "timestamp": int(ts / 1000),  # Convert ms to seconds
                    "price": price,
                }
                for ts, price in prices_raw
            ]
            
            logger.info(f"Fetched {len(prices)} price points for {token_address[:8]}...")
            
            # Cache the result
            self.cache[cache_key] = (prices, datetime.now(timezone.utc))
            
            return prices
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Token not found on CoinGecko: {token_address}")
                return []
            else:
                logger.error(f"CoinGecko API error: {e}")
                return []
        except Exception as e:
            logger.error(f"Error fetching price history: {e}")
            return []
    
    async def get_price_at_timestamp(
        self,
        token_address: str,
        target_timestamp: int,
        vs_currency: str = "usd",
    ) -> Optional[float]:
        """
        Get token price at a specific timestamp (approximation).
        
        Fetches price history and finds closest price point to target.
        
        Args:
            token_address: Token address
            target_timestamp: Unix timestamp
            vs_currency: Currency (default: usd)
            
        Returns:
            Price at timestamp, or None if not found
        """
        # Fetch last 90 days to ensure we capture target
        days_back = min(90, (datetime.now(timezone.utc).timestamp() - target_timestamp) / 86400 + 5)
        prices = await self.get_token_price_history(token_address, days=int(days_back), vs_currency=vs_currency)
        
        if not prices:
            return None
        
        # Find closest price point
        closest = min(prices, key=lambda p: abs(p["timestamp"] - target_timestamp))
        
        # Only accept if within 6 hours
        if abs(closest["timestamp"] - target_timestamp) > 21600:
            logger.warning(f"No price data within 6 hours of target timestamp")
            return None
        
        return closest["price"]
    
    async def get_current_prices(
        self,
        token_addresses: List[str],
        vs_currency: str = "usd",
    ) -> Dict[str, float]:
        """
        Get current prices for multiple tokens (batch request).
        
        Args:
            token_addresses: List of token addresses
            vs_currency: Currency (default: usd)
            
        Returns:
            Dict mapping address -> price
            
        Example:
            >>> api = CoinGeckoAPI()
            >>> prices = await api.get_current_prices([
            ...     "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
            ...     "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH
            ... ])
            >>> print(f"USDC: ${prices[USDC_ADDRESS]:.4f}")
        """
        # CoinGecko endpoint: /simple/token_price/ethereum
        url = f"{self.base_url}/simple/token_price/ethereum"
        
        # Normalize addresses
        addresses = [addr.lower() for addr in token_addresses]
        
        params = {
            "contract_addresses": ",".join(addresses),
            "vs_currencies": vs_currency,
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Parse response: {"0xabc...": {"usd": 1.23}, ...}
            result = {}
            for addr in addresses:
                if addr in data and vs_currency in data[addr]:
                    result[addr] = data[addr][vs_currency]
            
            logger.info(f"Fetched current prices for {len(result)} tokens")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching current prices: {e}")
            return {}
