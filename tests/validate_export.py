"""
Validation script to test DataExporter with MetricsPipeline integration.

This demonstrates the export functionality with real pipeline data
(or mocked data if API calls are not available).
"""
import asyncio
from services.data_exporter import DataExporter
from services.metrics_pipeline import MetricsPipeline
from pathlib import Path


async def test_export_with_pipeline():
    """Test export functionality with MetricsPipeline data."""
    print("=" * 80)
    print("TESTING DATA EXPORTER WITH METRICS PIPELINE")
    print("=" * 80)
    
    # Initialize services
    pipeline = MetricsPipeline()
    exporter = DataExporter()
    
    # Known pool for testing
    pool_address = "0x3de27efa2f1aa663ae5d458857e731c129069f29"
    
    try:
        print(f"\n🔍 Step 1: Fetching metrics for pool {pool_address[:10]}...")
        results = await pipeline.analyze_pool_with_competitors(pool_address)
        
        if results.get("input_pool"):
            print(f"✅ Got input pool: {results['input_pool'].get('pool_name')}")
            print(f"✅ Got {len(results.get('competitors', []))} competitors")
            print(f"✅ Metric groups: {len(results['input_pool'].get('metrics', {}))}")
        else:
            print("❌ No input pool data returned")
            return
        
        print(f"\n📊 Step 2: Exporting to Excel...")
        excel_path = exporter.export_to_excel(results)
        print(f"✅ Excel exported to: {excel_path}")
        
        # Verify file exists
        if Path(excel_path).exists():
            file_size = Path(excel_path).stat().st_size
            print(f"✅ File exists ({file_size:,} bytes)")
        else:
            print(f"❌ File not found: {excel_path}")
            return
        
        print(f"\n📄 Step 3: Exporting to CSV...")
        csv_path = exporter.export_to_csv(results)
        print(f"✅ CSV exported to: {csv_path}")
        
        # Verify file exists
        if Path(csv_path).exists():
            file_size = Path(csv_path).stat().st_size
            print(f"✅ File exists ({file_size:,} bytes)")
        else:
            print(f"❌ File not found: {csv_path}")
            return
        
        print(f"\n📋 Step 4: Verifying Excel structure...")
        import pandas as pd
        excel_file = pd.ExcelFile(excel_path)
        print(f"✅ Excel sheets: {excel_file.sheet_names}")
        
        # Check all_metrics sheet
        df_metrics = pd.read_excel(excel_path, sheet_name='all_metrics')
        print(f"✅ All metrics sheet: {len(df_metrics)} rows, {len(df_metrics.columns)} columns")
        print(f"   Columns: {list(df_metrics.columns)}")
        
        # Check summary sheet
        df_summary = pd.read_excel(excel_path, sheet_name='summary')
        print(f"✅ Summary sheet: {len(df_summary)} pools")
        
        print(f"\n📋 Step 5: Verifying CSV structure...")
        df_csv = pd.read_csv(csv_path)
        print(f"✅ CSV: {len(df_csv)} rows, {len(df_csv.columns)} columns")
        print(f"   Pool types: {df_csv['pool_type'].unique().tolist()}")
        print(f"   Unique pools: {df_csv['pool_name'].nunique()}")
        
        print(f"\n🗑️  Step 6: Testing cleanup...")
        # Test cleanup (with max_age=999 so it doesn't delete our new files)
        deleted = exporter.cleanup_old_exports(max_age_hours=999)
        print(f"✅ Cleanup tested (would delete {deleted} old files)")
        
        print(f"\n" + "=" * 80)
        print("✅ ALL VALIDATION TESTS PASSED!")
        print("=" * 80)
        print(f"\n📁 Export files location: {exporter.export_dir}")
        print(f"   Excel: {Path(excel_path).name}")
        print(f"   CSV: {Path(csv_path).name}")
        print(f"\n✅ You can now open these files to verify data quality!")
        
    except Exception as e:
        print(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()


async def test_export_with_mock_data():
    """Test export with mock data (fallback if API is not available)."""
    print("\n" + "=" * 80)
    print("TESTING DATA EXPORTER WITH MOCK DATA")
    print("=" * 80)
    
    # Create mock data matching pipeline format
    mock_results = {
        "input_pool": {
            "pool_name": "50WETH-50USDC Balancer Pool",
            "pool_address": "0x3de27efa2f1aa663ae5d458857e731c129069f29",
            "dex": "Balancer",
            "blockchain": "ethereum",
            "metrics": {
                "demand_usage": {
                    "total_traded_volume": 12345678.90,
                    "trade_count": 15432,
                    "avg_trade_size": 800.52,
                    "volume_7d": 8500000.00,
                    "volume_30d": 35000000.00,
                },
                "liquidity_depth": {
                    "tvl": 45678901.23,
                    "liquidity_score": 0.92,
                    "depth_2pct": 2000000.00,
                },
                "fee_monetization": {
                    "total_fees_collected": 123456.78,
                    "swap_fee_rate": 0.003,
                    "fee_apr": 0.025,
                }
            }
        },
        "competitors": [
            {
                "pool_name": "WETH/USDC UniSwap V3",
                "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
                "dex": "UniSwap",
                "blockchain": "ethereum",
                "metrics": {
                    "demand_usage": {
                        "total_traded_volume": 25000000.00,
                        "trade_count": 28000,
                    },
                    "liquidity_depth": {
                        "tvl": 55000000.00,
                    }
                }
            }
        ]
    }
    
    exporter = DataExporter()
    
    print(f"\n📊 Exporting mock data...")
    excel_path = exporter.export_to_excel(mock_results, filename="mock_test.xlsx")
    csv_path = exporter.export_to_csv(mock_results, filename="mock_test.csv")
    
    print(f"✅ Mock Excel: {excel_path}")
    print(f"✅ Mock CSV: {csv_path}")
    
    # Verify structure
    import pandas as pd
    df = pd.read_csv(csv_path)
    print(f"✅ Mock CSV has {len(df)} rows")
    print(f"✅ Pools in data: {df['pool_name'].unique().tolist()}")
    
    print(f"\n✅ MOCK DATA TEST PASSED!")


if __name__ == "__main__":
    print("🚀 Starting Data Exporter Validation Tests\n")
    
    # Run tests
    asyncio.run(test_export_with_mock_data())
    
    # Uncomment to test with real API data (requires API keys)
    # asyncio.run(test_export_with_pipeline())
    
    print(f"\n✅ All validation tests complete!")
