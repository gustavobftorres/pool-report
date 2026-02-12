"""
Manual validation script for Phase 4: Parameter Change Detection
Run this to test the pool_history_analyzer service.
"""
import asyncio
from services.pool_history_analyzer import PoolHistoryAnalyzer


async def test_phase_4():
    """Test parameter change detection with a real pool."""
    print("=" * 60)
    print("Phase 4: Parameter Change Detection - Manual Test")
    print("=" * 60)
    
    analyzer = PoolHistoryAnalyzer()
    
    # Test with a known Balancer pool address
    # Using a popular pool - WETH/USDC 50/50
    test_pool = "0x96646936b91d6B9D7D0c47C496AfBF3D6ec7B6f8"  # Example pool
    
    print(f"\n🔍 Testing with pool: {test_pool}")
    print(f"   Looking for changes in the last 30 days...\n")
    
    try:
        changes = await analyzer.detect_changes_in_period(test_pool, days=30)
        
        print(f"\n✅ Found {len(changes)} parameter changes\n")
        
        if changes:
            for i, change in enumerate(changes, 1):
                print(f"Change #{i}:")
                print(f"  Type: {change.change_type}")
                print(f"  Timestamp: {change.timestamp}")
                print(f"  Details: {change.details}")
                
                # Try to analyze impact
                try:
                    print(f"  📊 Analyzing impact...")
                    impact = await analyzer.analyze_impact_of_change(test_pool, change)
                    print(f"  Impact: {impact}")
                except Exception as e:
                    print(f"  ⚠️  Impact analysis failed: {e}")
                
                print()
        else:
            print("ℹ️  No parameter changes detected in the last 30 days.")
            print("   This could mean:")
            print("   - The pool has stable parameters")
            print("   - Event data is not available in the subgraph")
            print("   - The pool is relatively new")
        
        print("\n" + "=" * 60)
        print("✅ Phase 4 validation complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_phase_4())
