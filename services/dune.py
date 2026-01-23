from dune_client.client import DuneClient
from dune_client.query import QueryBase
from dune_client.types import QueryParameter

dune = DuneClient("U2Hthkbthz5AAEkvPmTV4mfx8sCSDtSF")

# Create query with parameters
query = QueryBase(
    query_id=6576923,
    params=[
        QueryParameter.text_type("blockchain", "ethereum"),
        QueryParameter.text_type("pool_address", "0x3de27efa2f1aa663ae5d458857e731c129069f29")
    ]
)

# Execute query
results = dune.run_query(query)

# Access results
print(f"Got {len(results.result.rows)} rows")