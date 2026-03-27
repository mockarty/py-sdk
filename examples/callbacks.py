"""Webhook and callback examples.

Mockarty can fire callbacks (webhooks) after a mock is matched:
  - HTTP callbacks (POST/PUT to external URLs)
  - Kafka callbacks (publish to a Kafka topic)
  - RabbitMQ callbacks (publish to an exchange/queue)

Callbacks support:
  - Retry logic (count + delay)
  - Trigger types (always, on_first_use, on_last_use)
  - Request data interpolation in callback body
"""

from mockarty import MockBuilder, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def http_callback(client: MockartyClient) -> None:
    """Fire an HTTP webhook after the mock is resolved."""
    mock = (
        MockBuilder.http("/api/orders", "POST")
        .id("order-with-webhook")
        .respond(201, body={
            "orderId": "$.fake.UUID",
            "status": "created",
        })
        .callback(
            url="https://hooks.example.com/order-created",
            method="POST",
            body={
                "event": "order.created",
                "orderId": "$.fake.UUID",
                "timestamp": "$.fake.DateISO",
            },
            headers={"X-Webhook-Secret": "s3cret"},
            timeout=5000,
            retry_count=3,
            retry_delay=1000,
        )
        .build()
    )
    client.mocks.create(mock)
    print("Created: POST /api/orders (with HTTP callback)")


def callback_with_trigger(client: MockartyClient) -> None:
    """Fire callback only on specific trigger conditions.

    Trigger types:
      - None/always: fire on every match
      - "on_first_use": fire only on the first match
      - "on_last_use": fire only when use_limiter reaches 0
    """
    mock = (
        MockBuilder.http("/api/trial/start", "POST")
        .id("trial-start-notify")
        .use_limiter(1)
        .respond(200, body={
            "trialId": "$.fake.UUID",
            "expiresIn": "7 days",
        })
        .callback(
            url="https://hooks.example.com/trial-started",
            method="POST",
            body={
                "event": "trial.started",
                "userId": "$.req.userId",
            },
            trigger="on_first_use",
        )
        .build()
    )
    client.mocks.create(mock)
    print("Created: POST /api/trial/start (callback on first use)")


def multiple_callbacks(client: MockartyClient) -> None:
    """Attach multiple callbacks to a single mock."""
    mock = (
        MockBuilder.http("/api/payments", "POST")
        .id("payment-multi-callback")
        .respond(200, body={
            "paymentId": "$.fake.UUID",
            "status": "processed",
        })
        # Notify the billing service
        .callback(
            url="https://billing.internal/payment-processed",
            method="POST",
            body={"paymentId": "$.fake.UUID", "amount": "$.req.amount"},
        )
        # Notify analytics
        .callback(
            url="https://analytics.internal/events",
            method="PUT",
            body={"event": "payment", "source": "mockarty"},
        )
        .build()
    )
    client.mocks.create(mock)
    print("Created: POST /api/payments (2 HTTP callbacks)")


def kafka_callback(client: MockartyClient) -> None:
    """Publish a Kafka message after mock resolution."""
    mock = (
        MockBuilder.http("/api/events/signup", "POST")
        .id("signup-kafka-callback")
        .respond(201, body={"userId": "$.fake.UUID"})
        .kafka_callback(
            brokers="kafka:9092",
            topic="user.events",
            body={
                "eventType": "USER_SIGNED_UP",
                "userId": "$.fake.UUID",
                "email": "$.req.email",
                "timestamp": "$.fake.DateISO",
            },
            key="$.req.email",
            headers={"X-Event-Source": "mockarty"},
        )
        .build()
    )
    client.mocks.create(mock)
    print("Created: POST /api/events/signup (Kafka callback)")


def rabbitmq_callback(client: MockartyClient) -> None:
    """Publish a RabbitMQ message after mock resolution."""
    mock = (
        MockBuilder.http("/api/notifications/send", "POST")
        .id("notification-rabbitmq-callback")
        .respond(202, body={"notificationId": "$.fake.UUID", "status": "queued"})
        .rabbitmq_callback(
            rabbit_url="amqp://guest:guest@rabbitmq:5672/",
            exchange="notifications",
            routing_key="email.send",
            body={
                "to": "$.req.email",
                "template": "$.req.template",
                "data": "$.req.data",
            },
        )
        .build()
    )
    client.mocks.create(mock)
    print("Created: POST /api/notifications/send (RabbitMQ callback)")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        http_callback(client)
        callback_with_trigger(client)
        multiple_callbacks(client)
        kafka_callback(client)
        rabbitmq_callback(client)

        # Clean up
        mock_ids = [
            "order-with-webhook", "trial-start-notify",
            "payment-multi-callback", "signup-kafka-callback",
            "notification-rabbitmq-callback",
        ]
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        print("\nAll callback example mocks cleaned up.")


if __name__ == "__main__":
    main()
