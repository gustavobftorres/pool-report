"""
Manual integration test for full report generation.
Run this to test the complete flow with real API calls.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.metrics_pipeline import MetricsPipeline
from services.data_exporter import DataExporter
from services.lp_return_calculator import LPReturnCalculator
from services.pool_history_analyzer import PoolHistoryAnalyzer


async def generate_full_report(pool_address: str):
    """Generate a complete report with all features."""
    print("="*70)
    print(f"FULL REPORT GENERATION TEST")
    print(f"Pool: {pool_address}")
    print("="*70)
    
    # Initialize services
    pipeline = MetricsPipeline()
    exporter = DataExporter()
    lp_calc = LPReturnCalculator()
    history_analyzer = PoolHistoryAnalyzer()
    
    # Phase 1 & 2: Metrics Pipeline with Boosted Support
    print("\n📊 PHASE 1-2: Metrics Pipeline")
    print("-" * 70)
    try:
        results = await pipeline.analyze_pool_with_competitors(pool_address)
        
        input_pool = results.get("input_pool")
        competitors = results.get("competitors", [])
        
        print(f"✅ Input Pool: {input_pool.get('pool_name')}")
        print(f"✅ Competitors Found: {len(competitors)}")
        for i, comp in enumerate(competitors[:3], 1):
            print(f"   {i}. {comp.get('pool_name')} ({comp.get('dex')})")
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        return
    
    # Phase 2: Export
    print("\n📁 PHASE 2: Data Export")
    print("-" * 70)
    try:
        excel_path = exporter.export_to_excel(results, filename="test_report.xlsx")
        csv_path = exporter.export_to_csv(results, filename="test_report.csv")
        print(f"✅ Excel: {excel_path}")
        print(f"✅ CSV: {csv_path}")
    except Exception as e:
        print(f"❌ Export failed: {e}")
    
    # Phase 3: Hold vs Pool
    print("\n💰 PHASE 3: Hold vs Pool Analysis")
    print("-" * 70)
    try:
        hold_vs_pool = await lp_calc.calculate_hold_vs_pool(pool_address, days=30)
        
        print(f"Hold Return:  {hold_vs_pool['hold_strategy']['return_pct']:>8.2f}%")
        print(f"Pool Return:  {hold_vs_pool['pool_strategy']['return_pct']:>8.2f}%")
        print(f"Winner:       {hold_vs_pool['comparison']['winner'].upper()}")
        print(f"Recommendation: {hold_vs_pool['comparison']['recommendation']}")
    except Exception as e:
        print(f"⚠️  Hold vs Pool failed: {e}")
    
    # Phase 4: Parameter Changes
    print("\n📅 PHASE 4: Parameter Change Detection")
    print("-" * 70)
    try:
        changes = await history_analyzer.detect_changes_in_period(pool_address, days=30)
        
        if changes:
            print(f"✅ Found {len(changes)} parameter changes:")
            for change in changes:
                change_time = datetime.fromtimestamp(change.timestamp, tz=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - change_time).days
                print(f"   - {change.change_type} ({days_ago} days ago)")
                if change.impact_summary:
                    print(f"     Impact: {change.impact_summary[:80]}...")
        else:
            print("ℹ️  No parameter changes in the last 30 days")
    except Exception as e:
        print(f"⚠️  Parameter detection failed: {e}")
    
    print("\n" + "="*70)
    print("REPORT GENERATION COMPLETE")
    print("="*70)


async def test_multiple_pools():
    """Test with multiple pools."""
    print("\n" + "="*70)
    print("TESTING WITH MULTIPLE POOLS")
    print("="*70)
    
    # List of test pools
    test_pools = [
        "0x3de27efa2f1aa663ae5d458857e731c129069f29",  # Known stable pool
        # Add more pools as needed
    ]
    
    for i, pool in enumerate(test_pools, 1):
        print(f"\n\n{'='*70}")
        print(f"POOL {i}/{len(test_pools)}")
        print(f"{'='*70}")
        await generate_full_report(pool)


if __name__ == "__main__":
    # Test with a known pool
    pool = "0x3de27efa2f1aa663ae5d458857e731c129069f29"
    
    # Run single pool test
    asyncio.run(generate_full_report(pool))
    
    # Uncomment to test multiple pools
    # asyncio.run(test_multiple_pools())
