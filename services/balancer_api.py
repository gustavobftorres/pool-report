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
    
    def _get_all_chains(self) -> list[tuple[str, str]]:
        """
        Get list of all available chains as (blockchain_name, api_chain) tuples.
        
        Returns:
            List of (blockchain_name, api_chain) tuples
        """
        return [
            ("ethereum", "MAINNET"),
            ("arbitrum", "ARBITRUM"),
            ("polygon", "POLYGON"),
            ("base", "BASE"),
            ("gnosis", "GNOSIS"),
            ("optimism", "OPTIMISM"),
            ("avalanche", "AVALANCHE"),
            ("zkevm", "ZKEVM"),
            ("mode", "MODE"),
            ("fraxtal", "FRAXTAL"),
            ("plasma", "PLASMA"),
        ]
    
    async def get_current_pool_data(self, pool_address: str, blockchain: str | None = None) -> Dict[str, Any]:
        """
        Get current pool data from Balancer GraphQL endpoint.
        Supports both V2 (via subgraph) and V3 (via API) automatically.
        If pool is not found on specified chain, tries all available chains.
        
        Args:
            pool_address: Ethereum address of the pool (42 chars)
            blockchain: Optional blockchain name (e.g., "ethereum", "arbitrum", "plasma")
                       If not provided, uses default from settings
            
        Returns:
            Dictionary containing pool data
        """
        # Determine which chains to try
        chains_to_try = []
        if blockchain:
            api_chain = self._blockchain_name_to_api_chain(blockchain)
            blockchain_name = blockchain.lower()
            chains_to_try = [(blockchain_name, api_chain)]
        else:
            api_chain = self.chain
            blockchain_name = self.blockchain_name
            chains_to_try = [(blockchain_name, api_chain)]
        
        # If not found, try all chains
        all_chains = self._get_all_chains()
        
        # Try V2 subgraph first (Ethereum only)
        if self.gql_endpoint:
            print(f"🔍 Querying V2 subgraph by address: {pool_address}")
            try:
                pool = await self._get_v2_pool_by_address(pool_address)
                if pool:
                    print(f"✅ Found V2 pool: {pool.get('name', pool.get('id'))}")
                    pool['_blockchain'] = "ethereum"
                    return pool
                else:
                    print(f"⚠️  Pool not found in V2 subgraph for address: {pool_address}")
            except Exception as e:
                print(f"⚠️  V2 query error for {pool_address}: {str(e)}")
        
<<<<<<< HEAD
        # Try V3 API on specified chain first, then all chains
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
=======
        #V3 API format
        try:
            query = """
            query GetPool($id: String!, $chain: GqlChain!) {
              poolGetPool(id: $id, chain: $chain) {
>>>>>>> @gbr/feat/takeaways
                id
                title
                apr
                type
<<<<<<< HEAD
=======
                version
                tags
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
>>>>>>> @gbr/feat/takeaways
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
        
        # Try specified chain first
        for blockchain_name, api_chain in chains_to_try:
            print(f"🔍 Querying pool {pool_address} on chain: {api_chain} ({blockchain_name})")
            try:
                variables = {
                    "id": pool_address.lower(),
                    "chain": api_chain
                }
                
                data = await self._execute_query(self.v3_api_url, query, variables)
                pool = data.get("poolGetPool")
                
                if pool:
                    print(f"✅ Found V3 pool: {pool.get('name')} on {blockchain_name}")
                    # Debug: log volume24h and fees24h from API
                    dynamic_data = pool.get("dynamicData", {})
                    if dynamic_data:
                        volume24h_api = dynamic_data.get("volume24h", "N/A")
                        fees24h_api = dynamic_data.get("fees24h", "N/A")
                        print(f"   📊 API returned - volume24h: {volume24h_api}, fees24h: {fees24h_api}")
                    # Add metadata for URL generation
                    pool['_api_version'] = 'v3'
                    pool['_blockchain'] = blockchain_name
                    return pool
            except Exception as e:
                print(f"⚠️  V3 API failed on {blockchain_name}: {str(e)}")
        
        # If not found on specified chain, try all other chains
        print(f"🔍 Pool not found on {blockchain_name}, trying all available chains...")
        for blockchain_name, api_chain in all_chains:
            # Skip if already tried
            if (blockchain_name, api_chain) in chains_to_try:
                continue
            
<<<<<<< HEAD
            print(f"   Trying {api_chain} ({blockchain_name})...")
            try:
                variables = {
                    "id": pool_address.lower(),
                    "chain": api_chain
                }
                
                data = await self._execute_query(self.v3_api_url, query, variables)
                pool = data.get("poolGetPool")
                
                if pool:
                    print(f"✅ Found V3 pool: {pool.get('name')} on {blockchain_name}")
                    # Debug: log volume24h and fees24h from API
                    dynamic_data = pool.get("dynamicData", {})
                    if dynamic_data:
                        volume24h_api = dynamic_data.get("volume24h", "N/A")
                        fees24h_api = dynamic_data.get("fees24h", "N/A")
                        print(f"   📊 API returned - volume24h: {volume24h_api}, fees24h: {fees24h_api}")
                    # Add metadata for URL generation
                    pool['_api_version'] = 'v3'
                    pool['_blockchain'] = blockchain_name
                    return pool
            except Exception as e:
                # Silently continue to next chain
                continue
=======
            data = await self._execute_query(self.v3_api_url, query, variables)
            pool = data.get("poolGetPool")
            
            if pool:
                print(f"✅ Found V3 pool: {pool.get('name')}")
                
                # Debug: Show tags if available
                tags = pool.get('tags', [])
                if tags:
                    print(f"🏷️  Pool tags: {tags}")
                
                # Add metadata for URL generation
                pool['_api_version'] = 'v3'
                pool['_blockchain'] = self.blockchain_name
                return pool
        except Exception as e:
            print(f"⚠️  V3 API failed: {str(e)}")
>>>>>>> @gbr/feat/takeaways
        
        raise BalancerAPIError(
            f"Pool not found: {pool_address} on any chain. "
            f"Tried V2 subgraph and V3 API on all available chains."
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
            "swapFee": v2_pool.get("swapFee", "0"),
            "_api_version": "v2", 
            "_blockchain": self.blockchain_name,
            "dynamicData": {
                "totalLiquidity": v2_pool.get("totalLiquidity", "0"),
                "volume24h": "0",
                "fees24h": "0",
                "aprItems": []
            },
            "allTokens": [
                {
                    "address": token.get("address"),
                    "symbol": token.get("symbol"),
                    "name": token.get("name", token.get("symbol")),
                    "weight": token.get("weight")
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
                    volume24h = float(snapshot.get("volume24h", 0))
                    fees24h = float(snapshot.get("fees24h", 0))
                    
                    cumulative_volume += volume24h
                    cumulative_fees += fees24h
                    
                    # Calculate fees24h/volume24h ratio (swap fee rate)
                    volume_fees_ratio = fees24h / volume24h if volume24h > 0 else 0.0
                    
                    normalized_snapshots.append({
                        "timestamp": timestamp,
                        "liquidity": snapshot.get("totalLiquidity", "0"),
                        "swapVolume": str(cumulative_volume),
                        "swapFees": str(cumulative_fees),
                        "swapsCount": 0,
                        "volume24h": str(volume24h),
                        "fees24h": str(fees24h),
                        "volumeFeesRatio": volume_fees_ratio
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
            
            # Calculate volume24h/fees24h ratio for each snapshot
            # For V2, we need to calculate 24h metrics from cumulative data
            for i, snapshot in enumerate(snapshots):
                swap_volume = float(snapshot.get("swapVolume", 0))
                swap_fees = float(snapshot.get("swapFees", 0))
                
                # Calculate 24h volume and fees by comparing with previous snapshot
                if i > 0:
                    prev_volume = float(snapshots[i-1].get("swapVolume", 0))
                    prev_fees = float(snapshots[i-1].get("swapFees", 0))
                    volume24h = swap_volume - prev_volume
                    fees24h = swap_fees - prev_fees
                else:
                    # First snapshot: use cumulative values as 24h estimate
                    volume24h = swap_volume
                    fees24h = swap_fees
                
                # Calculate fees24h/volume24h ratio (swap fee rate)
                volume_fees_ratio = fees24h / volume24h if volume24h > 0 else 0.0
                
                # Add calculated fields to snapshot
                snapshot["volume24h"] = str(volume24h)
                snapshot["fees24h"] = str(fees24h)
                snapshot["volumeFeesRatio"] = volume_fees_ratio
        
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
    
    async def get_pool_events(
        self,
        pool_address: str,
        event_types: list[str],
        start_timestamp: int,
        end_timestamp: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get pool events from Balancer subgraph.
        
        Args:
            pool_address: Pool address
            event_types: List of event types to fetch
            start_timestamp: Start time (Unix timestamp)
            end_timestamp: End time (Unix timestamp), defaults to now
            
        Event Types:
            - "SwapFeePercentageChanged": Swap fee changes
            - "WeightsGraduallyChanged": Weight adjustments
            - "TokenAdded": Token additions to pool
            - "TokenRemoved": Token removals from pool
            - "GaugeDeposit": Gauge/incentive deposits
            
        Returns:
            List of event dictionaries with timestamp, type, and details
        """
        if end_timestamp is None:
            end_timestamp = int(datetime.now().timestamp())
        
        # Note: Balancer V2 subgraph doesn't have a unified "events" table
        # We need to query specific event types separately based on pool type
        # For now, we'll focus on swap fee changes which can be derived from
        # pool state changes in poolSnapshots
        
        events = []
        
        # Query pool snapshots to detect fee changes
        # Get pool ID first (needed for subgraph queries)
        pool_id = pool_address
        if len(pool_address) == 42 and self.gql_endpoint:
            try:
                pool_data = await self._get_v2_pool_by_address(pool_address)
                if pool_data and pool_data.get("id"):
                    pool_id = pool_data["id"]
            except Exception as e:
                print(f"⚠️  Could not get full pool ID for events: {str(e)}")
        
        # Query pool historical states to detect parameter changes
        query = """
        query GetPoolHistory($poolId: String!, $startTime: Int!, $endTime: Int!) {
          poolHistoricalLiquidities(
            first: 1000
            orderBy: block
            orderDirection: asc
            where: {
              poolId: $poolId
              block_gte: $startTime
              block_lte: $endTime
            }
          ) {
            id
            block
            poolId {
              id
              swapFee
              poolType
            }
          }
        }
        """
        
        # Note: The Balancer subgraph has limited event tracking
        # Most parameter changes are detected by comparing pool states over time
        # For a production implementation, consider:
        # 1. Monitoring Pool contract events directly via Ethereum logs
        # 2. Using Balancer's events subgraph if available
        # 3. Tracking parameter changes in poolSnapshots
        
        # For this implementation, we'll detect changes by comparing snapshots
        try:
            snapshots = await self.get_pool_snapshots(pool_address, days_back=90)
            
            if not snapshots or len(snapshots) < 2:
                print(f"⚠️  Not enough snapshots to detect parameter changes")
                return events
            
            # Detect swap fee changes by comparing consecutive snapshots
            prev_snapshot = None
            for snapshot in snapshots:
                snapshot_time = int(snapshot.get("timestamp", 0))
                
                # Skip snapshots outside time range
                if snapshot_time < start_timestamp or snapshot_time > end_timestamp:
                    continue
                
                # For the first snapshot in range, we need to get the previous one
                if prev_snapshot is None:
                    prev_snapshot = snapshot
                    continue
                
                # Check for swap fee changes
                # Note: V2 subgraph snapshots don't include swapFee in every snapshot
                # We would need to query the pool state at each timestamp
                # For now, we'll return empty events and document this limitation
                
                prev_snapshot = snapshot
            
            print(f"ℹ️  Detected {len(events)} parameter changes from {len(snapshots)} snapshots")
            
        except Exception as e:
            print(f"⚠️  Error querying pool events: {str(e)}")
        
        # Return events sorted by timestamp (newest first)
        events.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
        
        return events
