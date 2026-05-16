# Copyright (c) 2026 Mockarty. All rights reserved.

"""DSL builder tests — focus on the fluent API surface."""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest

from mockarty.fuzz import (
    AssertNoCrash,
    AssertStatus,
    CustomMutator,
    Endpoint,
    Mutator,
    Protocol,
    Seed,
    Target,
)


def _make_target(name: str = "t") -> Target:
    return Target(name).http_endpoint("GET", "/")


def test_target_requires_non_empty_name():
    with pytest.raises(ValueError):
        Target("")


def test_target_returns_self_for_chaining():
    t = Target("t")
    assert t.description("x") is t
    assert t.namespace("ns") is t
    assert t.strategy("mutation") is t
    assert t.source_type("recorder") is t
    assert t.http_endpoint("GET", "/") is t


def test_http_endpoint_records_method_path_and_base_url():
    t = Target("t").http_endpoint("post", "/login", base_url="https://api")
    assert t.endpoint is not None
    assert t.endpoint.protocol is Protocol.HTTP
    assert t.endpoint.method == "POST"
    assert t.endpoint.path == "/login"
    assert t.endpoint.url == "https://api"


def test_grpc_endpoint_records_service_and_method():
    t = Target("t").grpc_endpoint(
        "UserService", "GetUser", address="localhost:9000", use_tls=True
    )
    assert t.endpoint and t.endpoint.protocol is Protocol.GRPC
    assert t.endpoint.service == "UserService"
    assert t.endpoint.rpc_method == "GetUser"
    assert t.endpoint.url == "localhost:9000"
    assert t.endpoint.use_tls is True


def test_graphql_kafka_rabbitmq_soap_ws_record_their_fields():
    g = Target("g").graphql_endpoint("https://api/gql", path="/gql")
    assert g.endpoint and g.endpoint.protocol is Protocol.GRAPHQL

    k = Target("k").kafka_endpoint("broker:9092", topic="orders")
    assert k.endpoint and k.endpoint.topic == "orders"

    rq = Target("r").rabbitmq_endpoint("amqp://q", queue="q1")
    assert rq.endpoint and rq.endpoint.queue == "q1"

    with pytest.raises(ValueError):
        Target("r").rabbitmq_endpoint("amqp://q")  # no queue or exchange

    s = Target("s").soap_endpoint("https://soap", soap_action="GetUser")
    assert s.endpoint and s.endpoint.soap_action == "GetUser"

    w = Target("w").websocket_endpoint("wss://ws", subprotocol="json")
    assert w.endpoint and w.endpoint.ws_subprotocol == "json"


def test_seeds_accept_seed_instances_strings_and_bytes():
    t = _make_target().seeds(
        [
            Seed("named", "body"),
            "anon-str",
            b"\x00\x01anon-bytes",
        ]
    )
    seeds = t.seeds_list
    assert len(seeds) == 3
    assert seeds[0].name == "named"
    assert seeds[1].name == "seed-1"
    assert seeds[1].payload == "anon-str"
    assert seeds[2].name == "seed-2"


def test_add_seed_appends_only_seed_instances():
    t = _make_target().seeds([Seed("a", "a")])
    t.add_seed(Seed("b", "b"))
    assert [s.name for s in t.seeds_list] == ["a", "b"]
    with pytest.raises(TypeError):
        t.add_seed("not-a-seed")  # type: ignore[arg-type]


def test_mutator_accepts_enum_custom_and_string():
    t = _make_target()
    t.mutator(Mutator.JSON)
    t.mutator(Mutator.custom("my-mut", {"depth": 3}))
    t.mutator("future_category")
    out = t.mutators_list
    assert out[0] is Mutator.JSON
    assert isinstance(out[1], CustomMutator)
    assert out[1].name == "my-mut"
    assert isinstance(out[2], CustomMutator)
    assert out[2].name == "future_category"

    with pytest.raises(ValueError):
        t.mutator("")
    with pytest.raises(TypeError):
        t.mutator(123)  # type: ignore[arg-type]


def test_mutators_bulk_replaces_existing():
    t = _make_target().mutator(Mutator.JSON)
    t.mutators([Mutator.XML, Mutator.SQLI])
    assert [m.value for m in t.mutators_list] == ["xml", "sqli"]


def test_assertion_chain_and_type_check():
    a1 = AssertStatus(range(200, 300))
    a2 = AssertNoCrash()
    t = _make_target().assertion(a1).assertion(a2)
    assert t.assertions_list == [a1, a2]
    with pytest.raises(TypeError):
        t.assertion("nope")  # type: ignore[arg-type]


def test_assertions_bulk_validates_each():
    t = _make_target()
    t.assertions([AssertNoCrash(), AssertStatus(200)])
    assert len(t.assertions_list) == 2
    with pytest.raises(TypeError):
        t.assertions([AssertNoCrash(), "nope"])  # type: ignore[list-item]


def test_duration_accepts_timedelta_int_float():
    t = _make_target()
    t.duration(timedelta(minutes=5))
    t.duration(30)  # 30 seconds
    t.duration(0.5)  # 500ms
    with pytest.raises(ValueError):
        t.duration(0)
    with pytest.raises(ValueError):
        t.duration(timedelta(seconds=-1))


def test_timeout_per_request_validation():
    t = _make_target().timeout_per_request(timedelta(seconds=10))
    with pytest.raises(ValueError):
        t.timeout_per_request(0)


def test_numeric_limits_reject_negative():
    t = _make_target()
    for setter in (t.max_requests, t.max_rps, t.concurrency, t.mutation_depth):
        with pytest.raises(ValueError):
            setter(-1)
        setter(0)  # zero is allowed (= unlimited)
        setter(10)


def test_response_time_alert_positive():
    t = _make_target().response_time_alert(timedelta(seconds=2))
    with pytest.raises(ValueError):
        t.response_time_alert(0)


def test_reporter_requires_name():
    t = _make_target().reporter("allure").reporter("junit")
    with pytest.raises(ValueError):
        t.reporter("")


def test_extra_requires_key():
    t = _make_target().extra("tag", "smoke")
    with pytest.raises(ValueError):
        t.extra("", "x")


def test_snapshot_is_independent():
    base = (
        _make_target("base")
        .description("base")
        .seeds([Seed("s1", "a")])
        .mutator(Mutator.JSON)
        .assertion(AssertStatus(200))
    )
    fork = base.snapshot()
    fork.description("fork").add_seed(Seed("s2", "b"))
    assert base._description == "base"  # not mutated
    assert len(base.seeds_list) == 1
    assert fork._description == "fork"
    assert len(fork.seeds_list) == 2


def test_target_building_is_thread_safe():
    """Spam .assertion(...) and .add_seed(...) from many threads and
    verify nothing is lost or duplicated.
    """
    t = _make_target()
    n = 200

    def add_assertions():
        for i in range(n):
            t.assertion(AssertStatus(200 + i % 5))

    def add_seeds():
        for i in range(n):
            t.add_seed(Seed(f"s-{threading.get_ident()}-{i}", str(i)))

    threads = [
        threading.Thread(target=add_assertions),
        threading.Thread(target=add_assertions),
        threading.Thread(target=add_seeds),
        threading.Thread(target=add_seeds),
    ]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert len(t.assertions_list) == 2 * n
    assert len(t.seeds_list) == 2 * n


def test_endpoint_equality_and_repr():
    e1 = Endpoint(Protocol.HTTP, method="GET", path="/")
    e2 = Endpoint(Protocol.HTTP, method="GET", path="/")
    assert e1 == e2
    assert hash(e1) == hash(e2)
    assert "http" in repr(e1)


def test_repr_includes_counts():
    t = (
        _make_target()
        .seeds([Seed("a", "")])
        .mutator(Mutator.JSON)
        .assertion(AssertNoCrash())
    )
    r = repr(t)
    assert "seeds=1" in r
    assert "mutators=1" in r
    assert "assertions=1" in r
