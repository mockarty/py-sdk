# Copyright (c) 2026 Mockarty. All rights reserved.

"""Example: describe a load test with the LoadTest builder DSL.

The builder emits either a k6-compatible script or a perf-config JSON carrying
the full load profile (stages/thresholds/env). It does not run anything itself
— a thin wrapper around the existing perf engine.

Run the generated config locally with the CLI::

    mockarty-cli perf run --from-config checkout.json
"""

from mockarty.builders import LoadTest


def main() -> None:
    profile = (
        LoadTest("checkout-load")
        .target("http://127.0.0.1:8080")
        .get("/health")
        .post("/cart", body={"sku": "abc", "qty": 2})
        .stages([("30s", 50), ("1m", 50), ("10s", 0)])
        .threshold("http_req_duration", "p(95)<800")
        .threshold("http_req_failed", "rate<0.01")
        .think_time(0.5)
    )

    # 1) Inspect the generated k6 script.
    print("--- k6 script ---")
    print(profile.to_k6_script())

    # 2) Save a perf-config and run it locally with the CLI:
    #      mockarty-cli perf run --from-config checkout.json
    profile.save("checkout.json")
    print("wrote checkout.json — run it with:")
    print("  mockarty-cli perf run --from-config checkout.json")

    # 3) (Optional) submit the same config to a Mockarty server via the SDK:
    #      from mockarty import MockartyClient, PerfConfig
    #      client = MockartyClient("http://localhost:5770", api_key="...")
    #      cfg = profile.to_perf_config()
    #      client.perf.run(PerfConfig(name=cfg["name"], script=cfg["script"]))


if __name__ == "__main__":
    main()
