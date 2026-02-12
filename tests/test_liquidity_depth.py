"""
Test script to debug liquidity_depth query (6576965) failure.
Compares it with a working query to understand the difference.
"""
from dune_client.client import DuneClient
from dune_client.query import QueryBase
from dune_client.types import QueryParameter
import os

# Get API key from environment
DUNE_API_KEY = os.getenv("DUNE_API_KEY", "U2Hthkbthz5AAEkvPmTV4mfx8sCSDtSF")

dune = DuneClient(DUNE_API_KEY)

# Test parameters
blockchain = "ethereum"
pool_address = "0x3de27efa2f1aa663ae5d458857e731c129069f29"

print("=" * 80)
print("Testing Working Query (demand_usage - 6576923)")
print("=" * 80)

# Test with a working query first
working_query = QueryBase(
    query_id=6576923,  # demand_usage - this one works
    params=[
        QueryParameter.text_type("blockchain", blockchain),
        QueryParameter.text_type("pool_address", pool_address.lower())
    ]
)

try:
    results = dune.run_query(working_query)
    print(f"✅ Working query succeeded: {len(results.result.rows)} rows")
except Exception as e:
    print(f"❌ Working query failed: {e}")

print("\n" + "=" * 80)
print("Testing Failing Query (liquidity_depth - 6576965)")
print("=" * 80)

# Test with the failing query
failing_query = QueryBase(
    query_id=6576965,  # liquidity_depth - this one fails
    params=[
        QueryParameter.text_type("blockchain", blockchain),
        QueryParameter.text_type("pool_address", pool_address.lower())
    ]
)

try:
    results = dune.run_query(failing_query)
    print(f"✅ Failing query succeeded: {len(results.result.rows)} rows")
except Exception as e:
    print(f"❌ Failing query error: {e}")
    print(f"   Error type: {type(e).__name__}")
    
    # Try to get more details
    if hasattr(e, 'response'):
        try:
            print(f"   Status code: {e.response.status_code}")
            print(f"   Response text: {e.response.text[:500]}")
            print(f"   URL: {e.response.url}")
        except:
            pass

# Note: execute() method is deprecated, using run_query() instead
