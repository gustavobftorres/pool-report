import pandas as pd
import time
from datetime import timedelta
from dune_client.types import QueryParameter
from dune_client.client import DuneClient
from dune_client.query import QueryBase

# 1. SETUP
QUERY_ID = 6570778

# 2. TIME WINDOW
START_DATE = pd.Timestamp("2020-01-01")
END_DATE = pd.Timestamp.now()
WINDOW_DAYS = 90

DUNE_API_KEY = "U2Hthkbthz5AAEkvPmTV4mfx8sCSDtSF"

# ==============================================================================
# 1. EXTRACTION ENGINE (Dune Only)
# ==============================================================================

def fetch_data_from_dune():
    dune = DuneClient(DUNE_API_KEY)
    all_rows = []
    
    current_start = START_DATE
    print(f"🚀 Starting Dune Direct Extraction ({START_DATE.date()} -> {END_DATE.date()})...")

    while current_start < END_DATE:
        current_end = current_start + timedelta(days=WINDOW_DAYS)
        
        # Format for Dune {{param}}
        p_start = current_start.strftime("%Y-%m-%d 00:00:00")
        p_end = current_end.strftime("%Y-%m-%d 00:00:00")
        
        print(f"   Extracting window: {p_start} -> {p_end}")
        
        query = QueryBase(
            query_id=QUERY_ID,
            params=[
                QueryParameter.text_type("start_time", p_start),
                QueryParameter.text_type("end_time", p_end)
            ]
        )
        
        try:
            results = dune.run_query(query)
            rows = results.result.rows
            if rows:
                all_rows.extend(rows)
                print(f"     ✅ Found {len(rows)} LBPs")
            else:
                print("     ⚠️ No data")
                
        except Exception as e:
            print(f"     ❌ Error: {e}")
            
        current_start = current_end
        time.sleep(1)

    return pd.DataFrame(all_rows)

output = fetch_data_from_dune()
print(output)