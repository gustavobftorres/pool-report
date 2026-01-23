"""
Test script for the metrics pipeline.
Demonstrates the full flow of analyzing a pool and its competitors.
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
from services.metrics_pipeline import MetricsPipeline
from services.dune_metrics import METRIC_GROUP_NAMES
from services.insights_generator import InsightsGenerator

# Configure logging to see all the debug logs
logging.basicConfig(
    level=logging.INFO,  # Set to logging.DEBUG for even more detail
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


async def main():
    """Run the metrics pipeline test."""
    # Default pool address (can be overridden via command line)
    default_pool = "0x3de27efa2f1aa663ae5d458857e731c129069f29"
    
    # Get pool address from command line or use default
    pool_address = sys.argv[1] if len(sys.argv) > 1 else default_pool
    
    print(f"Testing Metrics Pipeline")
    print(f"Pool Address: {pool_address}\n")
    
    # Initialize pipeline
    pipeline = MetricsPipeline()
    
    # Run analysis
    try:
        results = await pipeline.analyze_pool_with_competitors(pool_address)
        
        # Print results
        pipeline.print_metrics(results)
        
        # Export to Excel
        excel_filename = export_to_excel(results, pool_address)
        print(f"\n📊 Results exported to: {excel_filename}")
        
        # Generate insights using specialist LLMs
        print("\n" + "=" * 80)
        print("GENERATING INSIGHTS WITH SPECIALIST LLMs")
        print("=" * 80)
        insights_generator = InsightsGenerator()
        if insights_generator.enabled:
            try:
                insights = await insights_generator.generate_dune_metrics_insights(
                    results,
                    max_bullets=5
                )
                if insights:
                    print("\n🤖 AI-Generated Insights:")
                    print(insights)
                else:
                    print("\n⚠️  No insights generated (check OpenAI API key and configuration)")
            except Exception as e:
                print(f"\n❌ Error generating insights: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("\nℹ️  Insights generation disabled (set ENABLE_INSIGHTS=true and OPENAI_API_KEY in .env)")
        
        print("\n✅ Pipeline test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def sanitize_sheet_name(name: str, max_length: int = 31) -> str:
    """
    Sanitize sheet name for Excel (remove invalid characters, limit length).
    
    Args:
        name: Original sheet name
        max_length: Maximum length (Excel limit is 31)
        
    Returns:
        Sanitized sheet name
    """
    # Excel sheet name restrictions: no : \ / ? * [ ]
    invalid_chars = [':', '\\', '/', '?', '*', '[', ']']
    sanitized = name
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def export_to_excel(results: dict, pool_address: str) -> str:
    """
    Export metrics results to an Excel file.
    
    Args:
        results: Results dictionary from analyze_pool_with_competitors
        pool_address: Pool address for filename
        
    Returns:
        Path to the created Excel file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pool_metrics_{pool_address[:10]}_{timestamp}.xlsx"
    filepath = Path(filename)
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        # Export input pool
        if results.get("input_pool"):
            input_pool = results["input_pool"]
            pool_name = input_pool.get('pool_name', 'Unknown')[:20]
            sheet_name = sanitize_sheet_name(f"Input_{pool_name}")
            export_pool_metrics(writer, input_pool, sheet_name)
        
        # Export competitors
        competitors = results.get("competitors", [])
        for i, competitor in enumerate(competitors, 1):
            pool_name = competitor.get('pool_name', 'Unknown')[:15]
            sheet_name = sanitize_sheet_name(f"Comp{i}_{pool_name}")
            export_pool_metrics(writer, competitor, sheet_name)
    
    return str(filepath)


def export_pool_metrics(writer: pd.ExcelWriter, pool_data: dict, sheet_name: str):
    """
    Export a single pool's metrics to an Excel sheet.
    
    Args:
        writer: Excel writer object
        pool_data: Pool data dictionary with metrics
        sheet_name: Name for the Excel sheet
    """
    metrics = pool_data.get("metrics", {})
    
    # Start row counter
    start_row = 0
    
    # Write pool info header
    pool_info = pd.DataFrame({
        "Field": ["Pool Name", "Pool Address", "DEX", "Blockchain"],
        "Value": [
            pool_data.get("pool_name", "Unknown"),
            pool_data.get("pool_address", "Unknown"),
            pool_data.get("dex", "Unknown"),
            pool_data.get("blockchain", "Unknown"),
        ]
    })
    pool_info.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row)
    start_row += len(pool_info) + 2
    
    # Write each metric group
    for metric_group, group_name in METRIC_GROUP_NAMES.items():
        if metric_group not in metrics:
            continue
        
        metric_data = metrics[metric_group]
        
        # Write metric group header
        header_df = pd.DataFrame({group_name: [""]})
        header_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row)
        start_row += 1
        
        # Check for errors
        if "error" in metric_data:
            error_df = pd.DataFrame({"Error": [metric_data["error"]]})
            error_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row)
            start_row += len(error_df) + 2
            continue
        
        # Write metric data
        rows = metric_data.get("rows", [])
        if rows:
            # Convert rows to DataFrame
            # Handle different row formats
            if isinstance(rows[0], dict):
                # Rows are dictionaries
                df = pd.DataFrame(rows)
            elif isinstance(rows[0], list):
                # Rows are lists - try to infer column names from first row
                if len(rows) > 0:
                    df = pd.DataFrame(rows[1:], columns=rows[0] if len(rows) > 1 else None)
                else:
                    df = pd.DataFrame()
            else:
                # Single value rows
                df = pd.DataFrame({group_name: rows})
            
            if not df.empty:
                df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row)
                start_row += len(df) + 2
        else:
            # No data
            no_data_df = pd.DataFrame({"Status": ["No data returned"]})
            no_data_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row)
            start_row += len(no_data_df) + 2


if __name__ == "__main__":
    asyncio.run(main())
