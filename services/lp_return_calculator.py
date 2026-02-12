"""
LP Return Calculator: Compare pool returns vs holding tokens.

Calculates profitability of providing liquidity versus holding tokens
in a wallet over a specified time period (default: 30 days).
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from services.balancer_api import BalancerAPI
from services.metrics_calculator import MetricsCalculator
from services.coingecko_api import CoinGeckoAPI

logger = logging.getLogger(__name__)


class LPReturnCalculator:
    """Calculate and compare LP returns vs holding strategy."""
    
    def __init__(self):
        """Initialize calculator with required services."""
        self.balancer_api = BalancerAPI()
        self.metrics_calc = MetricsCalculator()
        self.price_api = CoinGeckoAPI()
    
    async def calculate_hold_vs_pool(
        self,
        pool_address: str,
        days: int = 30,
        initial_investment_usd: float = 10000.0,
    ) -> Dict[str, Any]:
        """
        Calculate returns for hold strategy vs pool strategy.
        
        Args:
            pool_address: Pool address to analyze
            days: Time period to analyze (default: 30)
            initial_investment_usd: Initial investment amount (default: $10,000)
            
        Returns:
            Dictionary with comparison data:
            {
                "period_days": 30,
                "initial_investment_usd": 10000.0,
                "hold_strategy": {
                    "final_value_usd": 11250.0,
                    "return_pct": 12.5,
                    "return_usd": 1250.0,
                },
                "pool_strategy": {
                    "final_value_usd": 13309.0,
                    "return_pct": 33.09,
                    "return_usd": 3309.0,
                    "breakdown": {
                        "fees_earned_usd": 892.0,
                        "incentives_earned_usd": 421.0,
                        "impermanent_loss_usd": -312.0,
                        "token_appreciation_usd": 2308.0,
                    }
                },
                "comparison": {
                    "difference_pct": 20.59,
                    "winner": "pool",  # or "hold"
                    "recommendation": "Providing liquidity was 20.59% more profitable"
                }
            }
            
        Example:
            >>> calc = LPReturnCalculator()
            >>> result = await calc.calculate_hold_vs_pool(
            ...     "0x3de27efa2f1aa663ae5d458857e731c129069f29",
            ...     days=30,
            ...     initial_investment_usd=10000
            ... )
            >>> print(result["comparison"]["recommendation"])
        """
        logger.info(f"Calculating hold vs pool for {pool_address[:8]}... over {days} days")
        
        # Step 1: Get current pool data
        pool_data = await self.balancer_api.get_current_pool_data(pool_address)
        tokens = pool_data.get("allTokens", [])
        
        if not tokens:
            logger.error("No tokens found in pool data")
            return self._empty_result()
        
        # Step 2: Calculate hold strategy returns
        hold_result = await self._calculate_hold_return(
            tokens=tokens,
            days=days,
            initial_investment_usd=initial_investment_usd,
        )
        
        # Step 3: Calculate pool strategy returns
        pool_result = await self._calculate_pool_return(
            pool_address=pool_address,
            pool_data=pool_data,
            tokens=tokens,
            days=days,
            initial_investment_usd=initial_investment_usd,
        )
        
        # Step 4: Compare and generate recommendation
        comparison = self._compare_strategies(hold_result, pool_result)
        
        return {
            "period_days": days,
            "initial_investment_usd": initial_investment_usd,
            "hold_strategy": hold_result,
            "pool_strategy": pool_result,
            "comparison": comparison,
        }
    
    async def _calculate_hold_return(
        self,
        tokens: List[Dict[str, Any]],
        days: int,
        initial_investment_usd: float,
    ) -> Dict[str, Any]:
        """
        Calculate return if tokens were held in wallet.
        
        Logic:
        1. Get token prices {days} ago
        2. Calculate how many tokens could be bought with initial investment
        3. Get current token prices
        4. Calculate current value of held tokens
        5. Return percentage and absolute returns
        """
        logger.info("Calculating hold strategy returns...")
        
        # Get token weights (default to equal weight if not specified)
        total_weight = sum(float(token.get("weight", 1.0 / len(tokens))) for token in tokens)
        
        initial_total_value = 0.0
        current_total_value = 0.0
        
        for token in tokens:
            token_address = token.get("address", "").lower()
            token_symbol = token.get("symbol", "Unknown")
            
            # Get weight for this token
            weight = float(token.get("weight", 1.0 / len(tokens)))
            weight_normalized = weight / total_weight
            
            # Calculate allocation for this token
            token_allocation_usd = initial_investment_usd * weight_normalized
            
            try:
                # Get historical prices
                prices = await self.price_api.get_token_price_history(token_address, days=days)
                
                if not prices or len(prices) < 2:
                    logger.warning(f"Insufficient price data for {token_symbol}")
                    # Assume no price change if data unavailable
                    initial_total_value += token_allocation_usd
                    current_total_value += token_allocation_usd
                    continue
                
                # Get initial and current prices
                initial_price = prices[0]["price"]
                current_price = prices[-1]["price"]
                
                logger.info(f"{token_symbol}: ${initial_price:.4f} -> ${current_price:.4f}")
                
                # Calculate tokens bought and current value
                tokens_bought = token_allocation_usd / initial_price
                token_current_value = tokens_bought * current_price
                
                initial_total_value += token_allocation_usd
                current_total_value += token_current_value
                
            except Exception as e:
                logger.error(f"Error calculating hold return for {token_symbol}: {e}")
                # Assume no change if error
                initial_total_value += token_allocation_usd
                current_total_value += token_allocation_usd
        
        # Calculate returns
        return_usd = current_total_value - initial_total_value
        return_pct = (return_usd / initial_total_value * 100) if initial_total_value > 0 else 0.0
        
        logger.info(f"Hold strategy: ${initial_total_value:.2f} -> ${current_total_value:.2f} ({return_pct:+.2f}%)")
        
        return {
            "final_value_usd": current_total_value,
            "return_pct": return_pct,
            "return_usd": return_usd,
        }
    
    async def _calculate_pool_return(
        self,
        pool_address: str,
        pool_data: Dict[str, Any],
        tokens: List[Dict[str, Any]],
        days: int,
        initial_investment_usd: float,
    ) -> Dict[str, Any]:
        """
        Calculate return from providing liquidity to pool.
        
        Logic:
        1. Get fees earned over period (from snapshots)
        2. Get incentives earned (from APR data)
        3. Calculate impermanent loss
        4. Add token appreciation (same as hold strategy)
        5. Return total with breakdown
        """
        logger.info("Calculating pool strategy returns...")
        
        # 1. Calculate fees earned
        fees_earned_usd = await self._calculate_fees_earned(pool_address, days, initial_investment_usd)
        
        # 2. Calculate incentives earned
        incentives_earned_usd = self._calculate_incentives_earned(pool_data, days, initial_investment_usd)
        
        # 3. Calculate impermanent loss
        il_usd = await self._calculate_impermanent_loss_usd(tokens, days, initial_investment_usd)
        
        # 4. Calculate token appreciation (same logic as hold, but accounting for pool rebalancing)
        token_appreciation_usd = await self._calculate_token_appreciation(tokens, days, initial_investment_usd)
        
        # 5. Total return
        total_return_usd = fees_earned_usd + incentives_earned_usd + il_usd + token_appreciation_usd
        return_pct = (total_return_usd / initial_investment_usd * 100) if initial_investment_usd > 0 else 0.0
        final_value_usd = initial_investment_usd + total_return_usd
        
        logger.info(f"Pool strategy: ${initial_investment_usd:.2f} -> ${final_value_usd:.2f} ({return_pct:+.2f}%)")
        logger.info(f"  Fees: ${fees_earned_usd:.2f}, Incentives: ${incentives_earned_usd:.2f}, IL: ${il_usd:.2f}, Appreciation: ${token_appreciation_usd:.2f}")
        
        return {
            "final_value_usd": final_value_usd,
            "return_pct": return_pct,
            "return_usd": total_return_usd,
            "breakdown": {
                "fees_earned_usd": fees_earned_usd,
                "incentives_earned_usd": incentives_earned_usd,
                "impermanent_loss_usd": il_usd,
                "token_appreciation_usd": token_appreciation_usd,
            }
        }
    
    async def _calculate_fees_earned(
        self,
        pool_address: str,
        days: int,
        initial_investment_usd: float,
    ) -> float:
        """
        Calculate fees earned from providing liquidity.
        
        Uses pool snapshots to get actual fee accumulation over the period.
        """
        try:
            snapshots = await self.balancer_api.get_pool_snapshots(pool_address, days_back=days)
            
            if snapshots and len(snapshots) >= 2:
                # Get oldest and newest snapshots
                oldest = snapshots[0]
                newest = snapshots[-1]
                
                # Calculate total fees accumulated
                oldest_fees = float(oldest.get("swapFees", 0))
                newest_fees = float(newest.get("swapFees", 0))
                total_pool_fees = newest_fees - oldest_fees
                
                # Calculate TVL to determine our share
                oldest_tvl = float(oldest.get("liquidity", 1))
                
                # Our share of fees (proportional to our investment)
                if oldest_tvl > 0:
                    our_share = initial_investment_usd / oldest_tvl
                    fees_earned = total_pool_fees * our_share
                    logger.info(f"Fees from snapshots: ${fees_earned:.2f} (pool total: ${total_pool_fees:.2f})")
                    return fees_earned
            
            # Fallback: Use APR-based estimation
            logger.warning("Using APR-based fee estimation (snapshots unavailable)")
            dynamic_data = await self.balancer_api.get_current_pool_data(pool_address)
            apr_items = dynamic_data.get("dynamicData", {}).get("aprItems", [])
            
            # Find swap fee APR
            fee_apr = 0.0
            for item in apr_items:
                if item.get("type") == "SWAP_FEE":
                    fee_apr = float(item.get("apr", 0))
                    break
            
            # Calculate fees from APR
            daily_rate = fee_apr / 365 / 100  # Convert APR to daily decimal rate
            fees_earned = initial_investment_usd * daily_rate * days
            
            logger.info(f"Fees from APR ({fee_apr:.2f}%): ${fees_earned:.2f}")
            return fees_earned
            
        except Exception as e:
            logger.error(f"Error calculating fees: {e}")
            return 0.0
    
    def _calculate_incentives_earned(
        self,
        pool_data: Dict[str, Any],
        days: int,
        initial_investment_usd: float,
    ) -> float:
        """
        Calculate incentives earned (BAL, partner tokens, etc.).
        
        Uses APR data to estimate incentives over the period.
        """
        try:
            apr_items = pool_data.get("dynamicData", {}).get("aprItems", [])
            
            # Sum all incentive APRs (STAKING, REWARD, IB_YIELD, etc.)
            incentive_types = ["STAKING", "REWARD", "IB_YIELD", "VOTING", "MERKL"]
            total_incentive_apr = 0.0
            
            for item in apr_items:
                item_type = item.get("type", "")
                if item_type in incentive_types:
                    apr_value = float(item.get("apr", 0))
                    total_incentive_apr += apr_value
                    logger.info(f"Found incentive: {item_type} = {apr_value:.2f}%")
            
            # Calculate incentives earned
            daily_rate = total_incentive_apr / 365 / 100  # Convert APR to daily decimal rate
            incentives_earned = initial_investment_usd * daily_rate * days
            
            logger.info(f"Incentives ({total_incentive_apr:.2f}% APR): ${incentives_earned:.2f}")
            return incentives_earned
            
        except Exception as e:
            logger.error(f"Error calculating incentives: {e}")
            return 0.0
    
    async def _calculate_impermanent_loss_usd(
        self,
        tokens: List[Dict[str, Any]],
        days: int,
        initial_investment_usd: float,
    ) -> float:
        """
        Calculate impermanent loss in USD.
        
        Returns negative value representing loss.
        """
        try:
            il_ratio = await self._calculate_impermanent_loss(tokens, days)
            il_usd = initial_investment_usd * il_ratio
            
            logger.info(f"Impermanent loss: {il_ratio*100:.2f}% = ${il_usd:.2f}")
            return il_usd
            
        except Exception as e:
            logger.error(f"Error calculating IL: {e}")
            return 0.0
    
    async def _calculate_impermanent_loss(
        self,
        tokens: List[Dict[str, Any]],
        days: int,
    ) -> float:
        """
        Calculate impermanent loss from price changes.
        
        Formula for 2-token pool with weights w1 and w2:
        IL = (w1 * (P1_final/P1_initial)^w1 + w2 * (P2_final/P2_initial)^w2)^(1/(w1+w2)) - 1
        
        For 50/50 pool (w1=w2=0.5):
        IL = 2 * sqrt(price_ratio) / (1 + price_ratio) - 1
        
        Returns:
            Impermanent loss as a decimal (e.g., -0.05 for -5%)
        """
        if len(tokens) != 2:
            # For pools with more than 2 tokens, IL calculation is complex
            # For now, return 0 (conservative estimate)
            logger.warning(f"IL calculation not implemented for {len(tokens)}-token pools")
            return 0.0
        
        try:
            # Get price data for both tokens
            initial_prices = {}
            current_prices = {}
            weights = {}
            
            for token in tokens:
                token_address = token.get("address", "").lower()
                token_symbol = token.get("symbol", "Unknown")
                weight = float(token.get("weight", 0.5))
                
                prices = await self.price_api.get_token_price_history(token_address, days=days)
                
                if not prices or len(prices) < 2:
                    logger.warning(f"Insufficient price data for IL calculation: {token_symbol}")
                    return 0.0
                
                initial_prices[token_symbol] = prices[0]["price"]
                current_prices[token_symbol] = prices[-1]["price"]
                weights[token_symbol] = weight
            
            # Get the two tokens
            token_symbols = list(initial_prices.keys())
            symbol1, symbol2 = token_symbols[0], token_symbols[1]
            
            # Calculate price ratios
            ratio1 = current_prices[symbol1] / initial_prices[symbol1]
            ratio2 = current_prices[symbol2] / initial_prices[symbol2]
            
            w1 = weights[symbol1]
            w2 = weights[symbol2]
            
            # Calculate IL using generalized formula
            # V_pool / V_hold = (w1 * ratio1^w1 + w2 * ratio2^w2) / (w1 * ratio1 + w2 * ratio2)
            
            # Pool value multiplier (with rebalancing)
            pool_multiplier = (w1 * (ratio1 ** w1) + w2 * (ratio2 ** w2))
            
            # Hold value multiplier (without rebalancing)
            hold_multiplier = (w1 * ratio1 + w2 * ratio2)
            
            # IL = pool_value / hold_value - 1
            if hold_multiplier > 0:
                il = (pool_multiplier / hold_multiplier) - 1.0
            else:
                il = 0.0
            
            logger.info(f"IL calculation: {symbol1} ratio={ratio1:.4f}, {symbol2} ratio={ratio2:.4f}, IL={il*100:.2f}%")
            
            return il
            
        except Exception as e:
            logger.error(f"Error in IL calculation: {e}")
            return 0.0
    
    async def _calculate_token_appreciation(
        self,
        tokens: List[Dict[str, Any]],
        days: int,
        initial_investment_usd: float,
    ) -> float:
        """
        Calculate token appreciation component for pool strategy.
        
        This is similar to hold return but accounts for pool rebalancing.
        """
        # For simplicity, use the same calculation as hold strategy
        # In reality, the pool rebalances as prices change
        hold_result = await self._calculate_hold_return(tokens, days, initial_investment_usd)
        return hold_result["return_usd"]
    
    def _compare_strategies(
        self,
        hold_result: Dict[str, Any],
        pool_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare two strategies and generate recommendation.
        
        Returns:
            {
                "difference_pct": float,
                "winner": "hold" | "pool",
                "recommendation": str,
            }
        """
        hold_return = hold_result.get("return_pct", 0)
        pool_return = pool_result.get("return_pct", 0)
        
        difference = pool_return - hold_return
        winner = "pool" if difference > 0 else "hold"
        
        if abs(difference) < 1.0:
            recommendation = f"Both strategies performed similarly (within 1%)"
        elif winner == "pool":
            recommendation = f"Providing liquidity was {abs(difference):.2f}% more profitable"
        else:
            recommendation = f"Holding tokens was {abs(difference):.2f}% more profitable"
        
        return {
            "difference_pct": difference,
            "winner": winner,
            "recommendation": recommendation,
        }
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure for error cases."""
        return {
            "period_days": 0,
            "initial_investment_usd": 0,
            "hold_strategy": {"final_value_usd": 0, "return_pct": 0, "return_usd": 0},
            "pool_strategy": {
                "final_value_usd": 0,
                "return_pct": 0,
                "return_usd": 0,
                "breakdown": {
                    "fees_earned_usd": 0,
                    "incentives_earned_usd": 0,
                    "impermanent_loss_usd": 0,
                    "token_appreciation_usd": 0,
                }
            },
            "comparison": {"difference_pct": 0, "winner": "unknown", "recommendation": "Insufficient data"},
        }
