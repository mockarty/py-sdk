"""System statistics and status examples.

Demonstrates:
  - Retrieving system statistics (request counts, latency, uptime)
  - Getting resource counts (mocks, namespaces, stores)
  - Checking system status and health
  - Querying available feature flags
  - Building a monitoring dashboard
"""

from mockarty import MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def get_system_stats(client: MockartyClient) -> None:
    """Retrieve system-wide statistics.

    Stats include request volume, latency percentiles,
    error rates, and other operational metrics.
    """
    stats = client.stats.get_stats()
    print("System statistics:")
    print(f"  Total requests:   {stats.get('totalRequests')}")
    print(f"  Matched:          {stats.get('matchedRequests')}")
    print(f"  Unmatched:        {stats.get('unmatchedRequests')}")
    print(f"  Avg latency (ms): {stats.get('avgLatencyMs')}")
    print(f"  P95 latency (ms): {stats.get('p95LatencyMs')}")
    print(f"  P99 latency (ms): {stats.get('p99LatencyMs')}")
    print(f"  Error rate:       {stats.get('errorRate')}%")
    print(f"  Uptime:           {stats.get('uptime')}")

    # Protocol breakdown
    if stats.get("byProtocol"):
        print("  By protocol:")
        for proto, count in stats["byProtocol"].items():
            print(f"    {proto}: {count}")


def get_resource_counts(client: MockartyClient) -> None:
    """Get counts of all resources in the system.

    Useful for capacity planning and monitoring growth.
    """
    counts = client.stats.get_counts()
    print("Resource counts:")
    print(f"  Mocks:            {counts.get('mocks')}")
    print(f"  Namespaces:       {counts.get('namespaces')}")
    print(f"  Global store:     {counts.get('globalStoreEntries')}")
    print(f"  Chain store:      {counts.get('chainStoreEntries')}")
    print(f"  Collections:      {counts.get('collections')}")
    print(f"  Test runs:        {counts.get('testRuns')}")
    print(f"  Fuzzing configs:  {counts.get('fuzzingConfigs')}")
    print(f"  Perf configs:     {counts.get('perfConfigs')}")
    print(f"  Recorder sessions:{counts.get('recorderSessions')}")
    print(f"  Undefined reqs:   {counts.get('undefinedRequests')}")
    print(f"  Agent tasks:      {counts.get('agentTasks')}")


def get_system_status(client: MockartyClient) -> None:
    """Get the current system status.

    Status includes service health, database connectivity,
    cache status, and background job states.
    """
    status = client.stats.get_status()
    print("System status:")
    print(f"  Overall:    {status.get('status')}")
    print(f"  Version:    {status.get('version')}")
    print(f"  Database:   {status.get('database')}")
    print(f"  Cache:      {status.get('cache')}")
    print(f"  gRPC:       {status.get('grpc')}")

    if status.get("backgroundJobs"):
        print("  Background jobs:")
        for job_name, job_status in status["backgroundJobs"].items():
            print(f"    {job_name}: {job_status}")


def get_feature_flags(client: MockartyClient) -> None:
    """Query available feature flags.

    Feature flags indicate which capabilities are enabled
    based on the license and configuration.
    """
    features = client.stats.get_features()
    print("Feature flags:")
    for feature, enabled in sorted(features.items()):
        status = "ENABLED" if enabled else "disabled"
        print(f"  {feature}: {status}")


# ---------------------------------------------------------------------------
# Monitoring Dashboard
# ---------------------------------------------------------------------------

def monitoring_dashboard(client: MockartyClient) -> None:
    """Build a simple monitoring dashboard from stats and status.

    This aggregates data from multiple endpoints to give a
    comprehensive view of the Mockarty instance.
    """
    print("=" * 60)
    print("  MOCKARTY MONITORING DASHBOARD")
    print("=" * 60)

    # Health
    health = client.health.check()
    print(f"\n  Server:  {health.status} (v{health.release_id})")

    # Status
    status = client.stats.get_status()
    print(f"  DB:      {status.get('database')}")
    print(f"  Cache:   {status.get('cache')}")

    # Counts
    counts = client.stats.get_counts()
    print(f"\n  Mocks:          {counts.get('mocks', 0):>6}")
    print(f"  Namespaces:     {counts.get('namespaces', 0):>6}")
    print(f"  Collections:    {counts.get('collections', 0):>6}")
    print(f"  Undefined:      {counts.get('undefinedRequests', 0):>6}")

    # Stats
    stats = client.stats.get_stats()
    total = stats.get("totalRequests", 0)
    matched = stats.get("matchedRequests", 0)
    match_rate = (matched / total * 100) if total > 0 else 0
    print(f"\n  Total requests: {total:>6}")
    print(f"  Match rate:     {match_rate:>5.1f}%")
    print(f"  Avg latency:    {stats.get('avgLatencyMs', 0):>5.1f}ms")
    print(f"  P99 latency:    {stats.get('p99LatencyMs', 0):>5.1f}ms")

    # Features
    features = client.stats.get_features()
    enabled_count = sum(1 for v in features.values() if v)
    print(f"\n  Features:       {enabled_count}/{len(features)} enabled")

    print("\n" + "=" * 60)


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== System Stats ===")
        get_system_stats(client)
        print()

        print("=== Resource Counts ===")
        get_resource_counts(client)
        print()

        print("=== System Status ===")
        get_system_status(client)
        print()

        print("=== Feature Flags ===")
        get_feature_flags(client)
        print()

        print("=== Monitoring Dashboard ===")
        monitoring_dashboard(client)
        print()

        print("Stats example complete.")


if __name__ == "__main__":
    main()
