"""
Performance profiling script for the metrics pipeline.
Identifies bottlenecks and optimization opportunities.
"""
import asyncio
import cProfile
import pstats
import time
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.metrics_pipeline import MetricsPipeline


async def profile_pipeline():
    """Profile the metrics pipeline."""
    pipeline = MetricsPipeline()
    pool_address = "0x3de27efa2f1aa663ae5d458857e731c129069f29"
    
    print("="*70)
    print("PERFORMANCE PROFILING")
    print("="*70)
    print(f"\nPool: {pool_address}")
    print("\nStarting profiling... This may take a few minutes.\n")
    
    start_time = time.time()
    
    try:
        await pipeline.analyze_pool_with_competitors(pool_address)
        elapsed_time = time.time() - start_time
        
        print("\n" + "="*70)
        print(f"✅ Pipeline completed in {elapsed_time:.2f} seconds")
        print("="*70)
        
        # Performance recommendations
        if elapsed_time > 120:
            print("\n⚠️  Performance Warning: Pipeline took over 2 minutes")
            print("\nRecommendations:")
            print("  1. Check for sequential API calls that could be parallelized")
            print("  2. Consider adding caching for frequently accessed data")
            print("  3. Review database query optimization")
        elif elapsed_time > 60:
            print("\nℹ️  Performance Note: Pipeline took over 1 minute")
            print("Consider optimization if this is a common use case")
        else:
            print("\n✅ Performance is acceptable")
            
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")


async def profile_components():
    """Profile individual components."""
    from services.balancer_api import BalancerAPI
    from services.dex_benchmarker import DEXBenchmarker
    from services.dune_metrics import DuneMetricsService
    
    pool_address = "0x3de27efa2f1aa663ae5d458857e731c129069f29"
    
    print("\n" + "="*70)
    print("COMPONENT-LEVEL PROFILING")
    print("="*70)
    
    # Profile Balancer API
    print("\n1️⃣  Balancer API")
    balancer = BalancerAPI()
    start = time.time()
    try:
        await balancer.get_pool_info(pool_address)
        print(f"   ⏱️  Time: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Profile DEX Benchmarker
    print("\n2️⃣  DEX Benchmarker")
    dex = DEXBenchmarker()
    start = time.time()
    try:
        # This would need token addresses from pool
        print("   ⏱️  Time: N/A (requires token data)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Profile Dune Metrics
    print("\n3️⃣  Dune Metrics Service")
    dune = DuneMetricsService()
    start = time.time()
    try:
        await dune.get_comprehensive_metrics(pool_address)
        print(f"   ⏱️  Time: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"   ❌ Failed: {e}")


def main():
    """Run profiling with cProfile."""
    print("\n🔍 Starting detailed profiling with cProfile...\n")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run the pipeline
    asyncio.run(profile_pipeline())
    
    profiler.disable()
    
    print("\n" + "="*70)
    print("TOP 20 SLOWEST FUNCTIONS")
    print("="*70 + "\n")
    
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)
    
    print("\n" + "="*70)
    print("TOP 20 MOST CALLED FUNCTIONS")
    print("="*70 + "\n")
    
    stats.sort_stats('calls')
    stats.print_stats(20)
    
    # Optional: Component profiling
    print("\n" + "="*70)
    print("COMPONENT PROFILING")
    print("="*70)
    
    asyncio.run(profile_components())


if __name__ == "__main__":
    main()
