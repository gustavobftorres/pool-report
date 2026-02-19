"""
Interactive test for AnchorTokenInfo.
Fetches REAL data from DefiLlama and exports to Google Spreadsheet.
"""
import asyncio
import os
import sys

# Add project root to path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.anchor_token_info import AnchorTokenInfo

async def main():
    print("=" * 60)
    print("⚓ Anchor Token Info - Interactive Real Data Test")
    print("=" * 60)
    print("Recommended addresses (Ethereum Mainnet):")
    print(" - USDC: 0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
    print(" - WETH: 0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
    print(" - wstETH: 0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0")
    print("-" * 60)

    token_address = input("Enter anchor token address: ").strip()
    if not token_address:
        print("❌ Error: Token address is required.")
        return

    blockchain = input("Enter blockchain (default: ethereum): ").strip() or "ethereum"

    service = AnchorTokenInfo()
    
    print(f"🚀 Fetching live data for {token_address}...")
    try:
        # We call get_token_data with debug=True to trigger the spreadsheet export
        df = await service.get_token_data(token_address, blockchain, debug=True)
        
        if not df.empty:
            print("✅ Success!")
            print(f"📊 Retrieved {len(df)} records.")
            
            # Print a small preview
            print("Preview (Top 5 rows):")
            print(df.head().to_string())
            
            print("📂 Data exported to Google Spreadsheet (Landing markets token info).")
        else:
            print("⚠️  No data found for this token. Check the address and network.")
            
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
