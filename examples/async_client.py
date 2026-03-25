"""Async client examples using AsyncMockartyClient.

Demonstrates:
  - async with context manager
  - Basic async CRUD
  - Concurrent mock creation with asyncio.gather
  - Parallel operations pattern
"""

import asyncio

from mockarty import AsyncMockartyClient, MockBuilder

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


async def basic_async_usage() -> None:
    """Basic async client usage with context manager."""
    async with AsyncMockartyClient(
        base_url=MOCKARTY_URL, api_key=API_KEY
    ) as client:
        # Health check
        health = await client.health.check()
        print(f"Server status: {health.status}")

        # Create a mock
        mock = (
            MockBuilder.http("/api/async-hello", "GET")
            .id("async-hello")
            .respond(200, body={"message": "Hello from async!"})
            .build()
        )
        result = await client.mocks.create(mock)
        print(f"Created mock: {result.mock.id}")

        # Retrieve it
        fetched = await client.mocks.get("async-hello")
        print(f"Fetched: {fetched.http.route}")

        # Delete it
        await client.mocks.delete("async-hello")
        print("Deleted mock.")


async def concurrent_mock_creation() -> None:
    """Create multiple mocks concurrently using asyncio.gather."""
    async with AsyncMockartyClient(
        base_url=MOCKARTY_URL, api_key=API_KEY
    ) as client:
        # Build 10 mocks
        mocks = []
        for i in range(10):
            mock = (
                MockBuilder.http(f"/api/items/{i}", "GET")
                .id(f"concurrent-item-{i}")
                .respond(200, body={
                    "itemId": i,
                    "name": f"Item {i}",
                    "price": "$.fake.Price",
                })
                .build()
            )
            mocks.append(mock)

        # Create all mocks concurrently
        results = await asyncio.gather(
            *[client.mocks.create(m) for m in mocks]
        )
        print(f"Created {len(results)} mocks concurrently")
        for r in results:
            print(f"  - {r.mock.id}: overwritten={r.overwritten}")

        # Clean up concurrently
        await asyncio.gather(
            *[client.mocks.delete(f"concurrent-item-{i}") for i in range(10)]
        )
        print("All concurrent mocks deleted.")


async def parallel_operations() -> None:
    """Run multiple independent API operations in parallel."""
    async with AsyncMockartyClient(
        base_url=MOCKARTY_URL, api_key=API_KEY
    ) as client:
        # Create a mock first
        mock = (
            MockBuilder.http("/api/parallel-test", "GET")
            .id("parallel-test")
            .tags("test", "parallel")
            .respond(200, body={"status": "ok"})
            .build()
        )
        await client.mocks.create(mock)

        # Run health check, mock list, and store read in parallel
        health_task = client.health.check()
        mocks_task = client.mocks.list(limit=5)
        store_task = client.stores.global_get()

        health, page, store = await asyncio.gather(
            health_task, mocks_task, store_task
        )

        print(f"Health: {health.status}")
        print(f"Mocks: {page.total} total, fetched {len(page.items)}")
        print(f"Global store keys: {len(store)}")

        # Clean up
        await client.mocks.delete("parallel-test")


async def async_store_operations() -> None:
    """Async Global Store and Chain Store operations."""
    async with AsyncMockartyClient(
        base_url=MOCKARTY_URL, api_key=API_KEY
    ) as client:
        # Global store
        await client.stores.global_set_many({
            "async.key1": "value1",
            "async.key2": "value2",
        })
        store = await client.stores.global_get()
        print(f"Global store: {store}")

        # Chain store
        chain_id = "async-chain-example"
        await client.stores.chain_set_many(chain_id, {
            "step": "initialized",
            "counter": 0,
        })
        chain = await client.stores.chain_get(chain_id)
        print(f"Chain store [{chain_id}]: {chain}")

        # Cleanup
        await client.stores.global_delete_many(["async.key1", "async.key2"])
        await client.stores.chain_delete_many(chain_id, ["step", "counter"])
        print("Async store operations cleaned up.")


async def async_batch_with_error_handling() -> None:
    """Batch operations with per-item error handling."""
    async with AsyncMockartyClient(
        base_url=MOCKARTY_URL, api_key=API_KEY
    ) as client:
        mock_ids = [f"batch-{i}" for i in range(5)]
        mocks = [
            MockBuilder.http(f"/api/batch/{i}", "GET")
            .id(mock_ids[i])
            .respond(200, body={"index": i})
            .build()
            for i in range(5)
        ]

        # Create with individual error handling
        results = await asyncio.gather(
            *[client.mocks.create(m) for m in mocks],
            return_exceptions=True,
        )

        created = 0
        failed = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"  Failed to create mock {mock_ids[i]}: {result}")
                failed += 1
            else:
                created += 1
        print(f"Batch create: {created} succeeded, {failed} failed")

        # Cleanup (also with error handling)
        cleanup_results = await asyncio.gather(
            *[client.mocks.delete(mid) for mid in mock_ids],
            return_exceptions=True,
        )
        deleted = sum(1 for r in cleanup_results if not isinstance(r, Exception))
        print(f"Cleanup: {deleted}/{len(mock_ids)} deleted")


async def main() -> None:
    print("=== Basic Async Usage ===")
    await basic_async_usage()
    print()

    print("=== Concurrent Mock Creation ===")
    await concurrent_mock_creation()
    print()

    print("=== Parallel Operations ===")
    await parallel_operations()
    print()

    print("=== Async Store Operations ===")
    await async_store_operations()
    print()

    print("=== Batch with Error Handling ===")
    await async_batch_with_error_handling()
    print()

    print("All async examples complete.")


if __name__ == "__main__":
    asyncio.run(main())
