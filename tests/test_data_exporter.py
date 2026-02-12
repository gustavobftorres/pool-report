"""
Unit tests for the DataExporter service.

Tests cover Excel export, CSV export, metrics flattening, summary generation,
anchor data integration, and cleanup functionality.
"""
import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from services.data_exporter import DataExporter


# Mock data for testing
@pytest.fixture
def mock_pipeline_results():
    """Mock results from MetricsPipeline."""
    return {
        "input_pool": {
            "pool_name": "50WETH-50USDC",
            "pool_address": "0x3de27efa2f1aa663ae5d458857e731c129069f29",
            "dex": "Balancer",
            "blockchain": "ethereum",
            "metrics": {
                "demand_usage": {
                    "total_traded_volume": 1234567.89,
                    "trade_count": 5432,
                    "avg_trade_size": 227.45,
                },
                "liquidity_depth": {
                    "tvl": 9876543.21,
                    "liquidity_score": 0.87,
                }
            }
        },
        "competitors": [
            {
                "pool_name": "USDC-WETH UniSwap",
                "pool_address": "0xabc123def456",
                "dex": "UniSwap",
                "blockchain": "ethereum",
                "metrics": {
                    "demand_usage": {
                        "total_traded_volume": 2345678.90,
                        "trade_count": 6789,
                    }
                }
            },
            {
                "pool_name": "WETH/USDC Curve",
                "pool_address": "0x789xyz123abc",
                "dex": "Curve",
                "blockchain": "ethereum",
                "metrics": {
                    "demand_usage": {
                        "total_traded_volume": 3456789.01,
                        "trade_count": 8901,
                    }
                }
            }
        ]
    }


@pytest.fixture
def mock_anchor_data():
    """Mock anchor token data."""
    return {
        "token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "token_symbol": "USDC",
        "markets": [
            {
                "protocol": "Aave",
                "chain": "ethereum",
                "apy": 0.0542,
                "tvl_usd": 123456789.0
            },
            {
                "protocol": "Compound",
                "chain": "ethereum",
                "apy": 0.0487,
                "tvl_usd": 98765432.0
            }
        ]
    }


@pytest.fixture
def exporter(tmp_path):
    """Create DataExporter with temp directory."""
    return DataExporter(export_dir=str(tmp_path))


# Test 1: Excel export creates file
def test_export_to_excel_creates_file(exporter, mock_pipeline_results):
    """Test that Excel export creates a file."""
    filepath = exporter.export_to_excel(mock_pipeline_results, filename="test.xlsx")
    
    assert Path(filepath).exists()
    assert Path(filepath).suffix == ".xlsx"


# Test 2: CSV export creates file  
def test_export_to_csv_creates_file(exporter, mock_pipeline_results):
    """Test that CSV export creates a file."""
    filepath = exporter.export_to_csv(mock_pipeline_results, filename="test.csv")
    
    assert Path(filepath).exists()
    assert Path(filepath).suffix == ".csv"


# Test 3: Excel has correct sheets
def test_excel_has_correct_sheets(exporter, mock_pipeline_results):
    """Test that Excel file has expected sheets."""
    filepath = exporter.export_to_excel(mock_pipeline_results, filename="test.xlsx")
    
    # Read Excel file
    excel_file = pd.ExcelFile(filepath)
    sheet_names = excel_file.sheet_names
    
    assert "all_metrics" in sheet_names
    assert "summary" in sheet_names


# Test 4: Excel with anchor data has anchor sheet
def test_excel_with_anchor_data(exporter, mock_pipeline_results, mock_anchor_data):
    """Test that anchor data creates additional sheet."""
    filepath = exporter.export_to_excel(
        mock_pipeline_results,
        anchor_data=mock_anchor_data,
        filename="test.xlsx"
    )
    
    excel_file = pd.ExcelFile(filepath)
    assert "anchor_tokens" in excel_file.sheet_names


# Test 5: Metrics are flattened correctly
def test_metrics_flattening(exporter, mock_pipeline_results):
    """Test that nested metrics are flattened to rows."""
    rows = exporter._flatten_metrics_to_rows(
        mock_pipeline_results["input_pool"],
        pool_type="Input Pool"
    )
    
    assert len(rows) > 0
    
    # Check row structure
    first_row = rows[0]
    assert "pool_name" in first_row
    assert "pool_address" in first_row
    assert "metric_group" in first_row
    assert "metric_name" in first_row
    assert "metric_value" in first_row
    assert "metric_unit" in first_row
    
    # Check values
    assert first_row["pool_name"] == "50WETH-50USDC"
    assert first_row["pool_type"] == "Input Pool"
    assert first_row["dex"] == "Balancer"


# Test 6: CSV contains all pools
def test_csv_contains_all_pools(exporter, mock_pipeline_results):
    """Test that CSV includes input pool and competitors."""
    filepath = exporter.export_to_csv(mock_pipeline_results, filename="test.csv")
    
    df = pd.read_csv(filepath)
    
    # Should have rows from input pool and competitors
    pool_types = df["pool_type"].unique()
    assert "Input Pool" in pool_types
    assert "Competitor" in pool_types
    
    # Check we have data from all 3 pools (1 input + 2 competitors)
    pool_names = df["pool_name"].unique()
    assert len(pool_names) == 3


# Test 7: Summary sheet has correct structure
def test_summary_sheet_structure(exporter, mock_pipeline_results):
    """Test that summary sheet has expected columns."""
    df_summary = exporter._create_summary_sheet(mock_pipeline_results)
    
    expected_columns = ["pool_name", "pool_address", "dex", "pool_type"]
    for col in expected_columns:
        assert col in df_summary.columns
    
    # Should have 3 rows (1 input + 2 competitors)
    assert len(df_summary) == 3


# Test 8: Cleanup deletes old files
def test_cleanup_old_exports(exporter, mock_pipeline_results):
    """Test that cleanup removes old files."""
    # Create some export files
    exporter.export_to_excel(mock_pipeline_results, filename="old1.xlsx")
    exporter.export_to_csv(mock_pipeline_results, filename="old2.csv")
    
    # Manually set file modification time to be old
    old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).timestamp()
    
    for filepath in exporter.export_dir.glob("*.*"):
        import os
        os.utime(filepath, (old_time, old_time))
    
    # Run cleanup (max_age=24 hours)
    deleted = exporter.cleanup_old_exports(max_age_hours=24)
    
    assert deleted == 2


# Test 9: Auto-generated filename format
def test_auto_generated_filename(exporter, mock_pipeline_results):
    """Test that auto-generated filenames follow expected format."""
    filepath = exporter.export_to_excel(mock_pipeline_results)
    
    filename = Path(filepath).name
    
    # Should contain: pool_metrics_<address>_<timestamp>.xlsx
    assert filename.startswith("pool_metrics_")
    assert filename.endswith(".xlsx")
    assert "_" in filename  # Has timestamp


# Test 10: Handle empty metrics gracefully
def test_handle_empty_metrics(exporter):
    """Test that exporter handles pools with no metrics."""
    empty_results = {
        "input_pool": {
            "pool_name": "Empty Pool",
            "pool_address": "0x000",
            "dex": "Unknown",
            "blockchain": "ethereum",
            "metrics": {}
        },
        "competitors": []
    }
    
    # Should not crash
    filepath = exporter.export_to_excel(empty_results, filename="empty.xlsx")
    assert Path(filepath).exists()
    
    # Read and verify it has summary sheet at least
    excel_file = pd.ExcelFile(filepath)
    assert "summary" in excel_file.sheet_names


# Test 11: Unit inference works correctly
def test_unit_inference(exporter):
    """Test that unit inference works for different metric types."""
    assert exporter._infer_unit("total_volume", 1000) == "USD"
    assert exporter._infer_unit("trade_count", 50) == "Count"
    assert exporter._infer_unit("swap_fee", 0.03) == "%"
    assert exporter._infer_unit("efficiency_ratio", 1.5) == "Ratio"
    assert exporter._infer_unit("tvl", 10000) == "USD"
    assert exporter._infer_unit("apr", 0.05) == "%"


# Test 12: Metric name formatting
def test_metric_name_formatting(exporter):
    """Test that metric names are properly formatted."""
    assert exporter._format_metric_name("total_traded_volume") == "Total Traded Volume"
    assert exporter._format_metric_name("trade_count") == "Trade Count"
    assert exporter._format_metric_name("avg_trade_size") == "Avg Trade Size"


# Test 13: Export handles metrics with errors
def test_export_with_error_metrics(exporter):
    """Test that exporter handles metric groups with errors."""
    results_with_error = {
        "input_pool": {
            "pool_name": "Test Pool",
            "pool_address": "0x123",
            "dex": "Balancer",
            "blockchain": "ethereum",
            "metrics": {
                "demand_usage": {
                    "error": "Failed to fetch data"
                },
                "liquidity_depth": {
                    "tvl": 1000000
                }
            }
        },
        "competitors": []
    }
    
    # Should handle error gracefully
    filepath = exporter.export_to_csv(results_with_error, filename="error_test.csv")
    assert Path(filepath).exists()
    
    # Read CSV and verify error is captured
    df = pd.read_csv(filepath)
    error_rows = df[df["metric_name"] == "Error"]
    assert len(error_rows) > 0


# Test 14: Multiple competitors are all exported
def test_multiple_competitors_exported(exporter, mock_pipeline_results):
    """Test that all competitors are included in export."""
    filepath = exporter.export_to_csv(mock_pipeline_results, filename="multi.csv")
    
    df = pd.read_csv(filepath)
    
    # Check all pool names are present
    pool_names = df["pool_name"].unique()
    assert "50WETH-50USDC" in pool_names
    assert "USDC-WETH UniSwap" in pool_names
    assert "WETH/USDC Curve" in pool_names


# Test 15: Timestamp is included in exports
def test_timestamp_in_export(exporter, mock_pipeline_results):
    """Test that timestamp is included in exported data."""
    filepath = exporter.export_to_csv(mock_pipeline_results, filename="timestamp.csv")
    
    df = pd.read_csv(filepath)
    
    # Check timestamp column exists
    assert "timestamp" in df.columns
    
    # Check timestamp format
    first_timestamp = df["timestamp"].iloc[0]
    assert "UTC" in first_timestamp


# Run tests
# pytest tests/test_data_exporter.py -v
