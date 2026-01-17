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
        # Use BALANCER_GQL_ENDPOINT if provided, otherwise use individual endpoints
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
    
    async def get_current_pool_data(self, pool_address: str) -> Dict[str, Any]:
        """
        Get current pool data from Balancer GraphQL endpoint.
        Supports both V2 (via subgraph) and V3 (via API) automatically.
        
        Args:
            pool_address: Ethereum address of the pool (42 chars)
            
        Returns:
            Dictionary containing pool data
        """
        # If using custom GQL endpoint, try V2 subgraph query format first
        if self.gql_endpoint:
            print(f"🔍 Querying V2 subgraph by address...")
            try:
                pool = await self._get_v2_pool_by_address(pool_address)
                if pool:
                    print(f"✅ Found V2 pool: {pool.get('name', pool.get('id'))}")
                    return pool
            except Exception as e:
                print(f"⚠️  V2 query failed: {str(e)}")
        
        # Try V3 API format
        print(f"🔍 Trying V3 API...")
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
                }
              }
            }
            """
            
            variables = {
                "id": pool_address.lower(),
                "chain": self.chain
            }
            
            data = await self._execute_query(self.v3_api_url, query, variables)
            pool = data.get("poolGetPool")
            
            if pool:
                print(f"✅ Found V3 pool: {pool.get('name')}")
                # Add metadata for URL generation
                pool['_api_version'] = 'v3'
                pool['_blockchain'] = self.blockchain_name
                return pool
        except Exception as e:
            print(f"⚠️  V3 API failed: {str(e)}")
        
        raise BalancerAPIError(
            f"Pool not found: {pool_address}. "
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
        # Use Bytes! type for address like in the working example
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
                    "name": token.get("name", token.get("symbol"))
                }
                for token in v2_pool.get("tokens", [])
            ]
        }
    
    async def get_pool_snapshots(
        self,
        pool_address: str,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get historical pool snapshots from Balancer V2 Subgraph.
        
        Args:
            pool_address: Pool address or full pool ID
            days_back: Number of days of historical data to fetch
            
        Returns:
            List of pool snapshots with timestamp, liquidity, volume, and fees
        """
        # First, try to get the full pool ID if we only have address
        pool_id = pool_address
        
        # If we have a 42-char address and using GQL endpoint, get full pool ID first
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
        target_timestamp: int
    ) -> Dict[str, Any] | None:
        """
        Get the pool snapshot closest to a specific timestamp.
        
        Args:
            pool_address: Ethereum address of the pool
            target_timestamp: Target Unix timestamp
            
        Returns:
            Pool snapshot data or None if not found
        """
        # Get snapshots around the target time (1 day window)
        start_ts = target_timestamp - 86400  # 1 day before
        end_ts = target_timestamp + 86400    # 1 day after
        
        query = """
        query GetSnapshotNearTime($poolId: String!, $startTime: Int!, $endTime: Int!) {
          poolSnapshots(
            first: 10
            orderBy: timestamp
            orderDirection: asc
            where: {
              pool: $poolId
              timestamp_gte: $startTime
              timestamp_lte: $endTime
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
            "poolId": pool_address.lower(),
            "startTime": start_ts,
            "endTime": end_ts
        }
        
        data = await self._execute_query(self.v2_subgraph_url, query, variables)
        snapshots = data.get("poolSnapshots", [])
        
        if not snapshots:
            return None
        
        # Find the snapshot closest to target_timestamp
        closest_snapshot = min(
            snapshots,
            key=lambda s: abs(int(s["timestamp"]) - target_timestamp)
        )
        
        return closest_snapshot
