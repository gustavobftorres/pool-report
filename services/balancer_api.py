"""
Balancer API service for querying pool data via GraphQL.
Handles both V3 API and V2 Subgraph queries.
"""
import httpx
from datetime import datetime, timedelta
from typing import Any, Dict, List
from config import settings


class BalancerAPIError(Exception):
    """Custom exception for Balancer API errors."""
    pass


class BalancerAPI:
    """Service for interacting with Balancer V2 and V3 APIs."""
    
    def __init__(self):
        self.gql_endpoint = settings.balancer_gql_endpoint
        self.v3_api_url = settings.balancer_v3_api
        self.v2_subgraph_url = self.gql_endpoint or settings.balancer_v2_subgraph
        self.chain = settings.default_chain  # For API queries (e.g., MAINNET)
        self.blockchain_name = settings.blockchain_name  # For balancer.fi URLs (e.g., ethereum)
        
        if self.gql_endpoint:
            print(f"🔗 Using Balancer GQL Endpoint: {self.gql_endpoint}")
    
    async def _execute_query(
        self,
        url: str,
        query: str,
        variables: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query against the specified endpoint.
        
        Args:
            url: GraphQL endpoint URL
            query: GraphQL query string
            variables: Query variables
            
        Returns:
            Query response data
            
        Raises:
            BalancerAPIError: If the query fails
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    url,
                    json={"query": query, "variables": variables or {}}
                )
                response.raise_for_status()
                
                result = response.json()
                
                if "errors" in result:
                    error_messages = [e.get("message", str(e)) for e in result["errors"]]
                    raise BalancerAPIError(f"GraphQL errors: {', '.join(error_messages)}")
                
                return result.get("data", {})
                
            except httpx.HTTPError as e:
                raise BalancerAPIError(f"HTTP error querying Balancer API: {str(e)}")
            except Exception as e:
                raise BalancerAPIError(f"Error querying Balancer API: {str(e)}")
    
    def _blockchain_name_to_api_chain(self, blockchain_name: str) -> str:
        """
        Convert blockchain name from URL format to API chain code.
        
        Examples:
            ethereum -> MAINNET
            arbitrum -> ARBITRUM
            polygon -> POLYGON
            base -> BASE
            plasma -> PLASMA
        """
        mapping = {
            "ethereum": "MAINNET",
            "arbitrum": "ARBITRUM",
            "polygon": "POLYGON",
            "base": "BASE",
            "gnosis": "GNOSIS",
            "optimism": "OPTIMISM",
            "avalanche": "AVALANCHE",
            "zkevm": "ZKEVM",
            "mode": "MODE",
            "fraxtal": "FRAXTAL",
            "plasma": "PLASMA",
        }
        return mapping.get(blockchain_name.lower(), blockchain_name.upper())
    
    async def get_current_pool_data(self, pool_address: str, blockchain: str | None = None) -> Dict[str, Any]:
        """
        Get current pool data from Balancer GraphQL endpoint.
        Supports both V2 (via subgraph) and V3 (via API) automatically.
        
        Args:
            pool_address: Ethereum address of the pool (42 chars)
            blockchain: Optional blockchain name (e.g., "ethereum", "arbitrum", "plasma")
                       If not provided, uses default from settings
            
        Returns:
            Dictionary containing pool data
        """
        # Determine which chain to use
        if blockchain:
            api_chain = self._blockchain_name_to_api_chain(blockchain)
            blockchain_name = blockchain.lower()
        else:
            api_chain = self.chain
            blockchain_name = self.blockchain_name
        
        print(f"🔍 Querying pool {pool_address} on chain: {api_chain} ({blockchain_name})")
        
        # Note: V2 subgraph is typically Ethereum-only, so skip if querying other chains
        if self.gql_endpoint and (not blockchain or blockchain.lower() == "ethereum"):
            print(f"🔍 Querying V2 subgraph by address: {pool_address}")
            try:
                pool = await self._get_v2_pool_by_address(pool_address)
                if pool:
                    print(f"✅ Found V2 pool: {pool.get('name', pool.get('id'))}")
                    pool['_blockchain'] = blockchain_name
                    return pool
                else:
                    print(f"⚠️  Pool not found in V2 subgraph for address: {pool_address}")
            except Exception as e:
                print(f"⚠️  V2 query error for {pool_address}: {str(e)}")
        elif blockchain and blockchain.lower() != "ethereum":
            print(f"⏭️  Skipping V2 subgraph (only supports Ethereum, querying {blockchain})")
        
        # Try V3 API format
        try:
            query = """
            query GetPool($id: String!, $chain: GqlChain!) {
              poolGetPool(id: $id, chain: $chain) {
                id
                address
                name
                type
                version
                dynamicData {
                  totalLiquidity
                  volume24h
                  fees24h
                  swapFee
                  aprItems {
                    id
                    title
                    apr
                    type
                  }
                }
                allTokens {
                  address
                  symbol
                  name
                  weight
                }
              }
            }
            """
            
            variables = {
                "id": pool_address.lower(),
                "chain": api_chain
            }
            
            data = await self._execute_query(self.v3_api_url, query, variables)
            pool = data.get("poolGetPool")
            
            if pool:
                print(f"✅ Found V3 pool: {pool.get('name')}")
                # Add metadata for URL generation
                pool['_api_version'] = 'v3'
                pool['_blockchain'] = blockchain_name
                return pool
        except Exception as e:
            print(f"⚠️  V3 API failed: {str(e)}")
        
        raise BalancerAPIError(
            f"Pool not found: {pool_address} on chain {api_chain}. "
            f"Tried both V2 subgraph and V3 API."
        )
    
    async def _get_v2_pool_by_address(self, pool_address: str) -> Dict[str, Any] | None:
        """
        Query V2 pool by address using subgraph format (matching working example).
        
        Args:
            pool_address: Pool address (42 chars, e.g., 0x3de27...)
            
        Returns:
            Pool data in normalized format
        """
        query = """
        query PoolByAddress($address: Bytes!) {
          pools(first: 1, where: { address: $address }) {
            id
            address
            name
            poolType
            swapFee
            totalLiquidity
            totalSwapVolume
            totalSwapFee
            tokens {
              address
              symbol
              name
              decimals
              balance
              weight
            }
          }
        }
        """
        
        variables = {
            "address": pool_address.lower()
        }
        
        data = await self._execute_query(self.v2_subgraph_url, query, variables)
        pools = data.get("pools", [])
        
        if not pools:
            return None
        
        v2_pool = pools[0]
        
        # Normalize V2 data to match V3 format for compatibility
        return {
            "id": v2_pool.get("id"),
            "address": v2_pool.get("address", pool_address),
            "name": v2_pool.get("name") or f"Pool {v2_pool.get('poolType', 'Unknown')}",
            "type": v2_pool.get("poolType", "Unknown"),
            "version": 2,
            "swapFee": v2_pool.get("swapFee", "0"),  # Add swap fee from V2 pool
            "_api_version": "v2",  # Add metadata for URL generation
            "_blockchain": self.blockchain_name,  # Blockchain name for balancer.fi URLs
            "dynamicData": {
                "totalLiquidity": v2_pool.get("totalLiquidity", "0"),
                "volume24h": "0",  # Not available in single query
                "fees24h": "0",
                "aprItems": []
            },
            "allTokens": [
                {
                    "address": token.get("address"),
                    "symbol": token.get("symbol"),
                    "name": token.get("name", token.get("symbol")),
                    "weight": token.get("weight")  # Include weight for weighted pools
                }
                for token in v2_pool.get("tokens", [])
            ]
        }
    
    async def get_v3_pool_snapshots(
        self,
        pool_address: str,
        days_back: int = 30,
        blockchain: str | None = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical pool snapshots from Balancer V3 API.
        
        Args:
            pool_address: Pool address
            days_back: Number of days of historical data to fetch
            
        Returns:
            List of pool snapshots with timestamp, liquidity, volume, and fees
        """
        # Calculate timestamp range
        end_timestamp = int(datetime.utcnow().timestamp())
        start_timestamp = int((datetime.utcnow() - timedelta(days=days_back)).timestamp())
        
        # Determine which chain to use
        if blockchain:
            api_chain = self._blockchain_name_to_api_chain(blockchain)
        else:
            api_chain = self.chain
        
        query = """
        query GetPoolSnapshots($id: String!, $chain: GqlChain!, $range: GqlPoolSnapshotDataRange!) {
          poolGetSnapshots(id: $id, chain: $chain, range: $range) {
            timestamp
            totalLiquidity
            volume24h
            fees24h
            sharePrice
          }
        }
        """
        
        # Determine which chain to use
        if blockchain:
            api_chain = self._blockchain_name_to_api_chain(blockchain)
        else:
            api_chain = self.chain
        
        variables = {
            "id": pool_address.lower(),
            "chain": api_chain,
            "range": "THIRTY_DAYS"
        }
        
        try:
            print(f"   Attempting V3 snapshot query with range: THIRTY_DAYS")
            print(f"   Query variables: id={pool_address.lower()}, chain={api_chain}")
            data = await self._execute_query(self.v3_api_url, query, variables)
            snapshots = data.get("poolGetSnapshots", [])
            
            if not snapshots:
                print(f"⚠️  No snapshots returned from V3 API (empty result)")
                return []
            
            # Normalize V3 snapshots to match V2 format
            normalized_snapshots = []
            cumulative_volume = 0
            cumulative_fees = 0
            
            for snapshot in snapshots:
                timestamp = int(snapshot.get("timestamp", 0))
                if timestamp >= start_timestamp:
                    cumulative_volume += float(snapshot.get("volume24h", 0))
                    cumulative_fees += float(snapshot.get("fees24h", 0))
                    
                    normalized_snapshots.append({
                        "timestamp": timestamp,
                        "liquidity": snapshot.get("totalLiquidity", "0"),
                        "swapVolume": str(cumulative_volume),
                        "swapFees": str(cumulative_fees),
                        "swapsCount": 0
                    })
            
            print(f"✅ Got {len(normalized_snapshots)} V3 snapshots")
            return normalized_snapshots
            
        except BalancerAPIError as e:
            error_msg = str(e)
            print(f"⚠️  V3 snapshots query failed: {error_msg}")
            if "GraphQL errors" in error_msg:
                print(f"   GraphQL Error Details: {error_msg}")
            print(f"   V3 historical snapshots may not be available through this API endpoint yet")
            print(f"   Falling back to estimated metrics based on 24h data")
            return []
        except Exception as e:
            print(f"⚠️  Unexpected error in V3 snapshots: {str(e)}")
            print(f"   Falling back to estimated metrics based on 24h data")
            return []
    
    async def get_pool_snapshots(
        self,
        pool_address: str,
        days_back: int = 30,
        pool_version: str | None = None,
        blockchain: str | None = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical pool snapshots from Balancer API (V2 or V3).
        
        Args:
            pool_address: Pool address or full pool ID
            days_back: Number of days of historical data to fetch
            pool_version: Pool version ("v2" or "v3"), auto-detected if None
            blockchain: Optional blockchain name (e.g., "ethereum", "arbitrum", "plasma")
            
        Returns:
            List of pool snapshots with timestamp, liquidity, volume, and fees
        """
        if pool_version == "v3":
            print(f"🔍 Fetching V3 snapshots for {pool_address}")
            return await self.get_v3_pool_snapshots(pool_address, days_back, blockchain=blockchain)
        

        pool_id = pool_address
        
        if len(pool_address) == 42 and self.gql_endpoint:
            try:
                pool_data = await self._get_v2_pool_by_address(pool_address)
                if pool_data and pool_data.get("id"):
                    pool_id = pool_data["id"]
                    print(f"✅ Got full pool ID: {pool_id}")
            except Exception as e:
                print(f"⚠️  Could not get full pool ID: {str(e)}")
        
        # Calculate timestamp for days_back
        timestamp_cutoff = int(
            (datetime.utcnow() - timedelta(days=days_back)).timestamp()
        )
        
        query = """
        query GetPoolSnapshots($poolId: String!, $timestamp: Int!) {
          poolSnapshots(
            first: 1000
            orderBy: timestamp
            orderDirection: asc
            where: {
              pool: $poolId
              timestamp_gte: $timestamp
            }
          ) {
            id
            timestamp
            liquidity
            swapVolume
            swapFees
            swapsCount
          }
        }
        """
        
        variables = {
            "poolId": pool_id.lower(),
            "timestamp": timestamp_cutoff
        }
        
        data = await self._execute_query(self.v2_subgraph_url, query, variables)
        
        snapshots = data.get("poolSnapshots", [])
        
        if not snapshots:
            print(f"⚠️  No historical snapshots found for pool {pool_id}")
        else:
            print(f"✅ Found {len(snapshots)} snapshots")
        
        return snapshots
    
    async def get_pool_swaps(
        self,
        pool_address: str,
        start_timestamp: int,
        end_timestamp: int
    ) -> List[Dict[str, Any]]:
        """
        Get swap events for a pool within a time range.
        
        Args:
            pool_address: Ethereum address of the pool
            start_timestamp: Start timestamp (Unix)
            end_timestamp: End timestamp (Unix)
            
        Returns:
            List of swap events
        """
        query = """
        query GetPoolSwaps($poolId: String!, $startTime: Int!, $endTime: Int!) {
          swaps(
            first: 1000
            orderBy: timestamp
            orderDirection: asc
            where: {
              poolId: $poolId
              timestamp_gte: $startTime
              timestamp_lte: $endTime
            }
          ) {
            id
            timestamp
            tokenIn
            tokenOut
            tokenAmountIn
            tokenAmountOut
            valueUSD
          }
        }
        """
        
        variables = {
            "poolId": pool_address.lower(),
            "startTime": start_timestamp,
            "endTime": end_timestamp
        }
        
        data = await self._execute_query(self.v2_subgraph_url, query, variables)
        
        return data.get("swaps", [])
    
    async def get_snapshot_at_timestamp(
        self,
        pool_address: str,
        target_timestamp: int,
        pool_version: str | None = None,
        blockchain: str | None = None
    ) -> Dict[str, Any] | None:
        """
        Get the pool snapshot closest to a specific timestamp.
        
        Args:
            pool_address: Ethereum address of the pool
            target_timestamp: Target Unix timestamp
            pool_version: Pool version ("v2" or "v3"), auto-detected if None
            blockchain: Optional blockchain name (e.g., "ethereum", "arbitrum", "plasma")
            
        Returns:
            Pool snapshot data or None if not found
        """
        # Get snapshots (will automatically use V2 or V3 based on pool_version)
        # Fetch 5 days of data to ensure we capture the target timestamp
        snapshots = await self.get_pool_snapshots(
            pool_address, 
            days_back=5,
            pool_version=pool_version,
            blockchain=blockchain
        )
        
        if not snapshots:
            return None
        
        # Filter snapshots within 1 day of target
        nearby_snapshots = [
            s for s in snapshots
            if abs(int(s.get("timestamp", 0)) - target_timestamp) <= 86400
        ]
        
        if not nearby_snapshots:
            # No snapshots close enough, return None
            return None
        
        # Find the snapshot closest to target_timestamp
        closest_snapshot = min(
            nearby_snapshots,
            key=lambda s: abs(int(s.get("timestamp", 0)) - target_timestamp)
        )
        
        return closest_snapshot
