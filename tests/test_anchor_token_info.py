"""
Tests for the AnchorTokenInfo service.
Mocks external API calls to DefiLlama and Dune Analytics.
"""
import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch, MagicMock

from services.anchor_token_info import AnchorTokenInfo

# Sample Mock Data
MOCK_TOKEN_ADDRESS = "0xExampleTokenAddress"
MOCK_BLOCKCHAIN = "ethereum"

MOCK_DEFILLAMA_RESPONSE = {
    "data": [
        {
            "chain": "Ethereum",
            "project": "Aave V3",
            "symbol": "WETH",
            "tvlUsd": 1_000_000,
            "apy": 3.5,
            "underlyingTokens": [MOCK_TOKEN_ADDRESS],
            "pool": "pool-uuid-1"
        },
        {
            "chain": "Ethereum",
            "project": "Compound V3",
            "symbol": "cWETH",
            "tvlUsd": 500_000,
            "apy": 2.1,
            "underlyingTokens": [MOCK_TOKEN_ADDRESS],
            "pool": "pool-uuid-2"
        },
        {
            "chain": "Arbitrum", # Different chain to test filtering/sorting
            "project": "Radiant",
            "symbol": "rdntETH",
            "tvlUsd": 100_000,
            "apy": 5.0,
            "underlyingTokens": [MOCK_TOKEN_ADDRESS],
            "pool": "pool-uuid-3"
        }
    ]
}

MOCK_DUNE_ROWS = [
    {
        "blockchain": "ethereum",
        "project_version": "2",  # Updated to match new Dune schema (version field returns '2', '3', etc.)
        "token_pair": "USDC-WETH",  # Pair format: OTHER_TOKEN-ANCHOR_TOKEN
        "total_volume_usd": 50000.0,
        "swap_count": 100
    },
    {
        "blockchain": "ethereum",
        "project_version": "3",  # Updated to match new Dune schema
        "token_pair": "DAI-WETH",
        "total_volume_usd": 75000.0,
        "swap_count": 150
    }
]

@pytest.fixture
def anchor_service():
    """Fixture to initialize the service with mocked dependencies."""
    with patch("services.anchor_token_info.BalancerAPI"), \
         patch("services.anchor_token_info.DuneMetricsService") as MockDune:
        
        service = AnchorTokenInfo()
        # Mock the internal Dune service instance
        service.dune_service = MockDune.return_value
        service.dune_service._execute_query = AsyncMock(return_value={"rows": []})
        service.dune_available = True
        return service

@pytest.mark.asyncio
async def test_get_lending_markets_success(anchor_service):
    """Test fetching and filtering lending markets from DefiLlama."""
    
    # Mock httpx.AsyncClient.get
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_DEFILLAMA_RESPONSE
        mock_get.return_value = mock_response

        markets = await anchor_service._get_lending_markets(MOCK_TOKEN_ADDRESS)
        
        assert len(markets) == 3
        # Check sorting by APY descending (Radiant 5.0 > Aave 3.5 > Compound 2.1)
        assert markets[0]["protocol"] == "Radiant"
        assert markets[0]["apy"] == 5.0
        assert markets[1]["protocol"] == "Aave V3"
        assert markets[2]["protocol"] == "Compound V3"

@pytest.mark.asyncio
async def test_get_historical_volume_success(anchor_service):
    """Test fetching volume data from Dune."""
    
    # Setup mock return for Dune
    anchor_service.dune_service._execute_query.return_value = {"rows": MOCK_DUNE_ROWS}
    
    # Mock settings to ensure query ID is present
    with patch("services.anchor_token_info.settings") as mock_settings:
        mock_settings.dune_anchor_volume_query_id = 12345
        
        volume_data = await anchor_service._get_historical_volume(MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN)
        
        assert len(volume_data) == 2
        assert volume_data[0]["token_pair"] == "USDC-WETH"
        assert volume_data[0]["total_volume_usd"] == 50000.0
        assert volume_data[0]["project_version"] == "2"  # Updated to match new schema

@pytest.mark.asyncio
async def test_get_historical_volume_no_query_id(anchor_service):
    """Test behavior when no Dune Query ID is configured."""
    
    with patch("services.anchor_token_info.settings") as mock_settings:
        # Simulate missing query ID
        del mock_settings.dune_anchor_volume_query_id 
        # Alternatively ensure getattr returns None by unsetting it on the mock object if needed, 
        # but the safest way for a mock object is setting it to None explicitly
        mock_settings.dune_anchor_volume_query_id = None
        
        volume_data = await anchor_service._get_historical_volume(MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN)
        assert volume_data == []
        # Ensure execute_query was NOT called
        anchor_service.dune_service._execute_query.assert_not_called()

@pytest.mark.asyncio
async def test_get_token_data_integration(anchor_service):
    """Test the main orchestrator merging logic."""
    
    # Mock both sub-calls
    with patch.object(anchor_service, "_get_lending_markets", new_callable=AsyncMock) as mock_lending, \
         patch.object(anchor_service, "_get_historical_volume", new_callable=AsyncMock) as mock_volume:
        
        # Scenario: We have both lending and volume data
        mock_lending.return_value = [
            {"protocol": "Aave V3", "apy": 3.5, "tvl_usd": 1000000}
        ]
        mock_volume.return_value = MOCK_DUNE_ROWS
        
        df = await anchor_service.get_token_data(MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN)
        
        assert not df.empty
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2  # Should correspond to volume rows
        
        # Check if volume columns exist
        assert "token_pair" in df.columns
        assert "total_volume_usd" in df.columns
        
        # Check if best lending market info was merged
        assert "best_market_protocol" in df.columns
        assert "best_market_apy" in df.columns
        assert df.iloc[0]["best_market_protocol"] == "Aave V3"
        assert df.iloc[0]["best_market_apy"] == 3.5

@pytest.mark.asyncio
async def test_get_token_data_lending_only(anchor_service):
    """Test orchestrator when only lending data is available (no volume)."""
    
    with patch.object(anchor_service, "_get_lending_markets", new_callable=AsyncMock) as mock_lending, \
         patch.object(anchor_service, "_get_historical_volume", new_callable=AsyncMock) as mock_volume:
        
        mock_lending.return_value = [{"protocol": "Aave V3", "apy": 3.5}]
        mock_volume.return_value = []
        
        df = await anchor_service.get_token_data(MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN)
        
        assert not df.empty
        assert len(df) == 1
        assert "protocol" in df.columns
        assert "apy" in df.columns
        assert "total_volume_usd" not in df.columns  # Volume cols shouldn't exist

@pytest.mark.asyncio
async def test_get_token_data_volume_only(anchor_service):
    """Test orchestrator when only volume data is available (no lending)."""
    
    with patch.object(anchor_service, "_get_lending_markets", new_callable=AsyncMock) as mock_lending, \
         patch.object(anchor_service, "_get_historical_volume", new_callable=AsyncMock) as mock_volume:
        
        mock_lending.return_value = []
        mock_volume.return_value = MOCK_DUNE_ROWS
        
        df = await anchor_service.get_token_data(MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN)
        
        assert not df.empty
        assert len(df) == 2
        assert "token_pair" in df.columns
        # Best market columns should NOT exist
        assert "best_market_project" not in df.columns

def test_get_summary_stats(anchor_service):
    """Test summary statistics generation."""
    
    data = {
        "apy": [3.5, 2.1, 5.0],
        "total_volume_usd": [100.0, 200.0, 300.0]
    }
    df = pd.DataFrame(data)
    
    stats = anchor_service.get_summary_stats(df)
    
    assert stats["total_markets"] == 3
    assert stats["max_apy"] == 5.0
    assert abs(stats["avg_apy"] - 3.53) < 0.1 # approx 3.533
    assert stats["cumulative_volume"] == 600.0

@pytest.mark.asyncio
async def test_get_token_data_debug_exports_to_spreadsheet(anchor_service):
    """Test that setting debug=True exports to Google Spreadsheet."""
    with patch.object(anchor_service, "_get_lending_markets", new_callable=AsyncMock) as mock_lending, \
         patch.object(anchor_service, "_get_historical_volume", new_callable=AsyncMock) as mock_volume, \
         patch("services.spreadsheet_service.export_dataframe_to_sheet") as mock_export:

        mock_lending.return_value = [{"protocol": "Aave V3", "apy": 3.5}]
        mock_volume.return_value = []

        df = await anchor_service.get_token_data(MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN, debug=True)

        mock_export.assert_called_once()
        call_args = mock_export.call_args
        assert call_args[0][0] is df
        assert not df.empty
        assert df.iloc[0]["protocol"] == "Aave V3"
