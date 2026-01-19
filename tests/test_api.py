"""
Simple test script to verify the Balancer API integration.
This can be run independently to test data fetching without starting the full server.
"""
import asyncio
from services.balancer_api import BalancerAPI
from services.metrics_calculator import MetricsCalculator


async def test_balancer_api():
    """Test fetching data from Balancer APIs."""
    
    # The pool address from the requirements
    pool_address = "0x3de27efa2f1aa663ae5d458857e731c129069f29"
    
    print("=" * 70)
    print("🧪 Testing Balancer API Integration")
    print("=" * 70)
    print(f"\n📊 Pool Address: {pool_address}\n")
    
    try:
        # Initialize API
        api = BalancerAPI()
        
        # Test 1: Get current pool data
        print("Test 1: Fetching current pool data from Balancer V3 API...")
        print("-" * 70)
        current_pool = await api.get_current_pool_data(pool_address)
        print(f"✅ Pool Name: {current_pool.get('name')}")
        print(f"✅ Pool Type: {current_pool.get('type')}")
        print(f"✅ Pool Version: {current_pool.get('version')}")
        
        dynamic_data = current_pool.get('dynamicData', {})
        print(f"✅ Current TVL: ${float(dynamic_data.get('totalLiquidity', 0)):,.2f}")
        print(f"✅ 24h Volume: ${float(dynamic_data.get('volume24h', 0)):,.2f}")
        print(f"✅ 24h Fees: ${float(dynamic_data.get('fees24h', 0)):,.2f}")
        
        apr_items = dynamic_data.get('aprItems', [])
        if apr_items:
            print(f"✅ APR Items: {len(apr_items)} found")
            for item in apr_items:
                print(f"   - {item.get('title')}: {float(item.get('apr', 0)) * 100:.2f}% ({item.get('type')})")
        
        # Test 2: Get historical snapshots
        print("\n\nTest 2: Fetching historical snapshots from V2 Subgraph...")
        print("-" * 70)
        snapshots = await api.get_pool_snapshots(pool_address, days_back=30)
        print(f"✅ Found {len(snapshots)} snapshots")
        
        if snapshots:
            oldest = snapshots[0]
            newest = snapshots[-1]
            print(f"✅ Oldest snapshot: {oldest.get('timestamp')} (Liquidity: ${float(oldest.get('liquidity', 0)):,.2f})")
            print(f"✅ Newest snapshot: {newest.get('timestamp')} (Liquidity: ${float(newest.get('liquidity', 0)):,.2f})")
        
        # Test 3: Calculate metrics
        print("\n\nTest 3: Calculating comprehensive metrics...")
        print("-" * 70)
        calculator = MetricsCalculator()
        metrics = await calculator.calculate_pool_metrics(pool_address)
        
        print(f"✅ Pool Name: {metrics.pool_name}")
        print(f"✅ TVL Current: ${metrics.tvl_current:,.2f}")
        print(f"✅ TVL 15 Days Ago: ${metrics.tvl_15_days_ago:,.2f}")
        print(f"✅ TVL Change: {metrics.tvl_change_percent:+.2f}%")
        print(f"✅ Volume (15 days): ${metrics.volume_15_days:,.2f}")
        print(f"✅ Fees (15 days): ${metrics.fees_15_days:,.2f}")
        if metrics.apr_current:
            print(f"✅ Current APR: {metrics.apr_current * 100:.2f}%")
        else:
            print(f"⚠️  APR: Not available")
        
        # Test 4: Format for email
        print("\n\nTest 4: Formatting metrics for email...")
        print("-" * 70)
        formatted = calculator.format_metrics_for_email(metrics)
        print("✅ Email data formatted successfully:")
        for key, value in formatted.items():
            print(f"   - {key}: {value}")
        
        print("\n" + "=" * 70)
        print("✅ All tests passed! The API integration is working correctly.")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print(f"❌ Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    print("\n🚀 Starting Balancer API Tests...\n")
    success = asyncio.run(test_balancer_api())
    
    if success:
        print("\n✨ Ready to start the FastAPI server and send emails!\n")
    else:
        print("\n⚠️  Please check the errors above.\n")
