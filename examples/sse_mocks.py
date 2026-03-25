"""SSE (Server-Sent Events) mock examples.

Demonstrates:
  - SSE event chain
  - Looping SSE stream
  - Heartbeat and max-time controls
"""

from mockarty import ContentResponse, Mock, MockartyClient, SSERequestContext
from mockarty.models.mock import SSEEvent, SSEEventChain

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def sse_event_chain(client: MockartyClient) -> None:
    """Stream a sequence of SSE events simulating a deployment pipeline."""
    mock = Mock(
        id="sse-deploy-pipeline",
        sse=SSERequestContext(
            event_path="/events/deploy",
            event_name="deploy",
        ),
        response=ContentResponse(
            status_code=200,
            sse_event_chain=SSEEventChain(
                events=[
                    SSEEvent(
                        event_name="build",
                        data={"step": "build", "status": "started"},
                        delay=0,
                    ),
                    SSEEvent(
                        event_name="build",
                        data={"step": "build", "status": "completed", "duration": "45s"},
                        delay=2000,
                    ),
                    SSEEvent(
                        event_name="test",
                        data={"step": "test", "status": "running", "total": 128},
                        delay=1000,
                    ),
                    SSEEvent(
                        event_name="test",
                        data={"step": "test", "status": "passed", "passed": 128, "failed": 0},
                        delay=3000,
                    ),
                    SSEEvent(
                        event_name="deploy",
                        data={"step": "deploy", "status": "completed", "version": "v2.1.0"},
                        delay=2000,
                    ),
                ],
            ),
        ),
    )
    client.mocks.create(mock)
    print("Created: SSE /events/deploy (event chain)")


def sse_looping_stream(client: MockartyClient) -> None:
    """Looping SSE stream that continuously sends heartbeat-like events.

    Loops every 5 seconds, up to 10 loops or 60 seconds total.
    """
    mock = Mock(
        id="sse-metrics-stream",
        sse=SSERequestContext(
            event_path="/events/metrics",
            event_name="metrics",
            description="Real-time metrics stream",
        ),
        response=ContentResponse(
            status_code=200,
            sse_event_chain=SSEEventChain(
                events=[
                    SSEEvent(
                        event_name="cpu",
                        data={"metric": "cpu", "value": 42.5, "unit": "percent"},
                        delay=0,
                    ),
                    SSEEvent(
                        event_name="memory",
                        data={"metric": "memory", "value": 67.3, "unit": "percent"},
                        delay=1000,
                    ),
                    SSEEvent(
                        event_name="disk",
                        data={"metric": "disk", "value": 35.1, "unit": "percent"},
                        delay=1000,
                    ),
                ],
                loop=True,
                loop_delay=5000,
                max_loops=10,
                max_time=60,
            ),
        ),
    )
    client.mocks.create(mock)
    print("Created: SSE /events/metrics (looping stream)")


def sse_with_heartbeat(client: MockartyClient) -> None:
    """SSE stream with heartbeat to keep the connection alive."""
    mock = Mock(
        id="sse-notifications",
        sse=SSERequestContext(
            event_path="/events/notifications",
        ),
        response=ContentResponse(
            status_code=200,
            sse_event_chain=SSEEventChain(
                events=[
                    SSEEvent(
                        event_name="notification",
                        data={"type": "info", "message": "New message received"},
                        id="1",
                        delay=0,
                    ),
                    SSEEvent(
                        event_name="notification",
                        data={"type": "warning", "message": "Disk usage above 80%"},
                        id="2",
                        delay=5000,
                    ),
                ],
                heartbeat=15,
                max_time=120,
            ),
        ),
    )
    client.mocks.create(mock)
    print("Created: SSE /events/notifications (with heartbeat)")


def sse_chat_simulation(client: MockartyClient) -> None:
    """Simulate an LLM chat streaming response via SSE."""
    mock = Mock(
        id="sse-chat-stream",
        sse=SSERequestContext(
            event_path="/chat/stream",
            event_name="chat",
        ),
        response=ContentResponse(
            status_code=200,
            sse_event_chain=SSEEventChain(
                events=[
                    SSEEvent(
                        event_name="delta",
                        data={"content": "Hello"},
                        delay=0,
                    ),
                    SSEEvent(
                        event_name="delta",
                        data={"content": "! How"},
                        delay=100,
                    ),
                    SSEEvent(
                        event_name="delta",
                        data={"content": " can I"},
                        delay=100,
                    ),
                    SSEEvent(
                        event_name="delta",
                        data={"content": " help you"},
                        delay=100,
                    ),
                    SSEEvent(
                        event_name="delta",
                        data={"content": " today?"},
                        delay=100,
                    ),
                    SSEEvent(
                        event_name="done",
                        data={"finish_reason": "stop", "usage": {"tokens": 8}},
                        delay=50,
                    ),
                ],
            ),
        ),
    )
    client.mocks.create(mock)
    print("Created: SSE /chat/stream (chat simulation)")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        sse_event_chain(client)
        sse_looping_stream(client)
        sse_with_heartbeat(client)
        sse_chat_simulation(client)

        # Clean up
        mock_ids = [
            "sse-deploy-pipeline", "sse-metrics-stream",
            "sse-notifications", "sse-chat-stream",
        ]
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        print("\nAll SSE example mocks cleaned up.")


if __name__ == "__main__":
    main()
