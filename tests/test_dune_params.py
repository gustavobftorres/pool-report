"""
Test script to verify Dune parameter passing for anchor token query.
"""
from dune_client.types import QueryParameter
from dune_client.client import DuneClient
from dune_client.query import QueryBase
from config import settings

def test_anchor_query():
    """Test the anchor token volume query with parameters."""
    
    # Initialize client
    api_key = settings.dune_api_key
    if not api_key:
        print("❌ No Dune API key found in settings")
        return
        
    client = DuneClient(api_key)
    query_id = 6664013
    
    # Test parameters
    token_address = "a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"  # USDC without 0x
    blockchain = "ethereum"
    token_symbol = "USDC"
    
    print(f"🔍 Testing Dune Query {query_id}")
    print(f"   Token Address: {token_address}")
    print(f"   Blockchain: {blockchain}")
    print(f"   Token Symbol: {token_symbol}")
    print()
    
    # Create parameters
    query_params = [
        QueryParameter.text_type("token_address", token_address),
        QueryParameter.text_type("blockchain", blockchain),
        QueryParameter.text_type("token_symbol_placeholder", token_symbol),
    ]
    
    print("📋 Parameters being sent:")
    for qp in query_params:
        print(f"   - {qp.key} = '{qp.value}' (type: {qp.type})")
    print()
    
    # Create query
    query = QueryBase(
        query_id=query_id,
        params=query_params
    )
    
    print("🚀 Executing query...")
    try:
        results = client.run_query(query)
        rows = results.result.rows if hasattr(results, 'result') and hasattr(results.result, 'rows') else []
        
        print(f"✅ Query succeeded!")
        print(f"   Rows returned: {len(rows)}")
        
        if rows:
            print(f"\n   First row:")
            for key, value in rows[0].items():
                print(f"      {key}: {value}")
        else:
            print(f"   ⚠️ No data returned (but query executed successfully)")
            
    except Exception as e:
        print(f"❌ Query failed: {str(e)}")
        print(f"\n💡 This error suggests the Dune query needs to be updated:")
        print(f"   1. Go to https://dune.com/queries/{query_id}")
        print(f"   2. Ensure parameters are declared at the top:")
        print(f"      {{{{token_address}}}} (text)")
        print(f"      {{{{blockchain}}}} (text)")
        print(f"      {{{{token_symbol_placeholder}}}} (text)")
        print(f"   3. Update line 9 to: WHERE contract_address = from_hex('{{{{token_address}}}}')")
        print(f"                                                        ^^                ^^")
        print(f"                                                        Add quotes!")

if __name__ == "__main__":
    test_anchor_query()
