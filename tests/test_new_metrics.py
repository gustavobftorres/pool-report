"""
Test script for new pool metrics feature.
"""
import asyncio
import sys
sys.path.insert(0, '/Users/gustavotorres/Desktop/Projects/personal/pool-report')

from services.balancer_api import BalancerAPI
from services.metrics_calculator import MetricsCalculator

async def test_single_v2_pool():
    """Test fetching single V2 pool with new metrics."""
    print("=" * 60)
    print("Testing Single Pool (V2)")
    print("=" * 60)
    
    pool_address = "0x3de27efa2f1aa663ae5d458857e731c129069f29"
    
    try:
        calculator = MetricsCalculator()
        metrics = await calculator.calculate_pool_metrics(pool_address)
        
        print(f"\n✅ Pool: {metrics.pool_name}")
        print(f"   Type: {metrics.pool_type}")
        print(f"   Swap Fee: {metrics.swap_fee * 100:.4f}%")
        print(f"   APR: {metrics.apr_current * 100:.2f}%" if metrics.apr_current else "   APR: N/A")
        print(f"   TVL: ${metrics.tvl_current:,.2f} ({metrics.tvl_change_percent:+.2f}%)")
        print(f"   Volume (15d): ${metrics.volume_15_days:,.2f} ({metrics.volume_change_percent:+.2f}%)")
        print(f"   Fees (15d): ${metrics.fees_15_days:,.2f} ({metrics.fees_change_percent:+.2f}%)")
        
        if metrics.token_weights:
            print(f"   Weights: {metrics.token_weights}")
        
        if metrics.boosted_apr:
            print(f"   Boosted APR: {metrics.boosted_apr * 100:.2f}%")
        
        print(f"   URL: {metrics.pool_url}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

async def test_multi_pool():
    """Test fetching multiple pools with rankings."""
    print("\n" + "=" * 60)
    print("Testing Multiple Pools")
    print("=" * 60)
    
    pool_addresses = [
        "0x3de27efa2f1aa663ae5d458857e731c129069f29",
        "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56",
        "0x96646936b91d6b9d7d0c47c496afbf3d6ec7b6f8"
    ]
    
    try:
        calculator = MetricsCalculator()
        multi_metrics = await calculator.calculate_multi_pool_metrics(
            pool_addresses,
            ranking_by=["swap_fee"]
        )
        
        print(f"\n✅ Processed {len(multi_metrics.pools)} pools")
        print(f"   Total Fees: ${multi_metrics.total_fees:,.2f}")
        print(f"   Weighted APR: {multi_metrics.total_apr * 100:.2f}%")
        
        print("\nTop 3 by Volume:")
        for name, volume, pct, url in multi_metrics.top_3_by_volume:
            print(f"   - {name}: ${volume:,.2f} ({pct:.1f}%)")
        
        if "swap_fee" in multi_metrics.custom_rankings:
            print("\nTop 3 by Swap Fee:")
            for name, fee, url in multi_metrics.custom_rankings["swap_fee"]:
                print(f"   - {name}: {fee * 100:.2f}%")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

async def test_single_v3_pool():
    """Test fetching single V3 pool with new metrics."""
    print("\n" + "=" * 60)
    print("Testing Single Pool (V3)")
    print("=" * 60)
    
    pool_address = "0x85b2b559bc2d21104c4defdd6efca8a20343361d"
    
    try:
        calculator = MetricsCalculator()
        metrics = await calculator.calculate_pool_metrics(pool_address)
        
        print(f"\n✅ Pool: {metrics.pool_name}")
        print(f"   Type: {metrics.pool_type}")
        print(f"   Swap Fee: {metrics.swap_fee * 100:.4f}%")
        print(f"   APR: {metrics.apr_current * 100:.2f}%" if metrics.apr_current else "   APR: N/A")
        print(f"   TVL: ${metrics.tvl_current:,.2f} ({metrics.tvl_change_percent:+.2f}%)")
        print(f"   Volume (15d): ${metrics.volume_15_days:,.2f} ({metrics.volume_change_percent:+.2f}%)")
        print(f"   Fees (15d): ${metrics.fees_15_days:,.2f} ({metrics.fees_change_percent:+.2f}%)")
        
        if metrics.token_weights:
            print(f"   Weights: {metrics.token_weights}")
        
        if metrics.boosted_apr:
            print(f"   Boosted APR: {metrics.boosted_apr * 100:.2f}%")
        
        print(f"   URL: {metrics.pool_url}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all tests."""
    await test_single_v2_pool()
    await test_single_v3_pool()
    await test_multi_pool()

if __name__ == "__main__":
    asyncio.run(main())
