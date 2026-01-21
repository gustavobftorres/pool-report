from dune_client.client import DuneClient

dune = DuneClient(api_key="U2Hthkbthz5AAEkvPmTV4mfx8sCSDtSF")

results = dune.execute(
    query_id=6576923,
    performance="medium", 
    params={
        "blockchain": "ethereum",
        "pool_address": "0x3de27efa2f1aa663ae5d458857e731c129069f29"
    }
)

print(f"Got {len(results.rows)} rows")