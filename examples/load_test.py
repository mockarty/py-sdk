# Copyright (c) 2026 Mockarty. All rights reserved.

"""Example: describe a load test with the LoadTest builder DSL.

The builder emits either a k6-compatible script or a perf-config JSON carrying
the full load profile (stages/thresholds/env). It does not run anything itself
— a thin wrapper around the existing perf engine.

Run the generated config locally with the CLI::

    mockarty-cli perf run --from-config checkout.json
"""

from mockarty import PerfConfig, PerfOptions, PerfStage
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

    # 3) A saved profile uses the typed options envelope. That keeps reusable
    #    run controls, including an opt-in metrics sink, in one server object.
    saved = PerfConfig(
        name="checkout soak",
        script=profile.to_k6_script(),
        options=PerfOptions(
            stages=[
                PerfStage(duration="30s", target=50),
                PerfStage(duration="1m", target=50),
                PerfStage(duration="10s", target=0),
            ],
            metrics_push=["prometheus:https://metrics.example.test/push"],
            metrics_push_interval="10s",
        ),
    )
    # client.perf.create_config(saved)
    print(saved.model_dump_json(by_alias=True, exclude_none=True, indent=2))


if __name__ == "__main__":
    main()
