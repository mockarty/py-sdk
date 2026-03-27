"""Messaging protocol mock examples: Kafka, RabbitMQ, SMTP.

Demonstrates:
  - Kafka topic mock with output routing
  - RabbitMQ queue mock with output routing
  - SMTP mock with sender/recipient conditions
"""

from mockarty import (
    AssertAction,
    ContentResponse,
    KafkaRequestContext,
    Mock,
    MockBuilder,
    MockartyClient,
    RabbitMQRequestContext,
    SmtpRequestContext,
)
from mockarty.models.condition import Condition
from mockarty.models.contexts import RabbitMQOutputProps

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


# ---------------------------------------------------------------------------
# Kafka
# ---------------------------------------------------------------------------

def kafka_topic_mock(client: MockartyClient) -> None:
    """Mock a Kafka consumer that responds to messages on a topic."""
    mock = (
        MockBuilder.kafka("order.events")
        .id("kafka-order-events")
        .respond(200, body={
            "eventId": "$.fake.UUID",
            "type": "ORDER_PROCESSED",
            "orderId": "$.req.orderId",
            "timestamp": "$.fake.DateISO",
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: Kafka topic order.events")


def kafka_with_conditions(client: MockartyClient) -> None:
    """Kafka mock that matches only specific message contents."""
    mock = (
        MockBuilder.kafka("payment.requests")
        .id("kafka-payment-requests")
        .condition("amount", AssertAction.NOT_EMPTY)
        .condition("currency", AssertAction.EQUALS, "USD")
        .respond(200, body={
            "transactionId": "$.fake.UUID",
            "status": "APPROVED",
            "processedAt": "$.fake.DateISO",
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: Kafka topic payment.requests (with conditions)")


def kafka_with_output_routing(client: MockartyClient) -> None:
    """Kafka mock that routes responses to an output topic.

    When a message matches, the response is published to the output topic.
    """
    mock = Mock(
        id="kafka-order-router",
        kafka=KafkaRequestContext(
            topic="order.incoming",
            output_topic="order.processed",
            output_brokers="kafka:9092",
            output_key="$.req.orderId",
        ),
        response=ContentResponse(
            status_code=200,
            payload={
                "orderId": "$.req.orderId",
                "status": "ROUTED",
                "processedBy": "mockarty",
            },
        ),
    )
    client.mocks.create(mock)
    print("Created: Kafka order.incoming -> order.processed (output routing)")


# ---------------------------------------------------------------------------
# RabbitMQ
# ---------------------------------------------------------------------------

def rabbitmq_queue_mock(client: MockartyClient) -> None:
    """Mock a RabbitMQ consumer listening on a queue."""
    mock = (
        MockBuilder.rabbitmq("notifications.queue")
        .id("rabbitmq-notifications")
        .respond(200, body={
            "notificationId": "$.fake.UUID",
            "channel": "email",
            "recipient": "$.req.email",
            "status": "SENT",
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: RabbitMQ queue notifications.queue")


def rabbitmq_with_output(client: MockartyClient) -> None:
    """RabbitMQ mock with output exchange/routing key for response messages."""
    mock = Mock(
        id="rabbitmq-order-processor",
        rabbitmq=RabbitMQRequestContext(
            queue="orders.pending",
            output_url="amqp://guest:guest@rabbitmq:5672/",
            output_exchange="orders.exchange",
            output_routing_key="orders.completed",
            output_props=RabbitMQOutputProps(
                delivery_mode=2,
                content_type="application/json",
                correlation_id="$.req.correlationId",
            ),
        ),
        response=ContentResponse(
            status_code=200,
            payload={
                "orderId": "$.req.orderId",
                "status": "COMPLETED",
                "completedAt": "$.fake.DateISO",
            },
        ),
    )
    client.mocks.create(mock)
    print("Created: RabbitMQ orders.pending -> orders.completed (output)")


# ---------------------------------------------------------------------------
# SMTP
# ---------------------------------------------------------------------------

def smtp_mock(client: MockartyClient) -> None:
    """Mock an SMTP server with sender/recipient conditions."""
    mock = Mock(
        id="smtp-welcome-email",
        smtp=SmtpRequestContext(
            server_name="email-server",
            sender_conditions=[
                Condition(
                    path="from",
                    assert_action=AssertAction.CONTAINS,
                    value="@myapp.com",
                ),
            ],
            subject_conditions=[
                Condition(
                    path="subject",
                    assert_action=AssertAction.CONTAINS,
                    value="Welcome",
                ),
            ],
        ),
        response=ContentResponse(
            status_code=200,
            payload={
                "messageId": "$.fake.UUID",
                "status": "DELIVERED",
                "deliveredAt": "$.fake.DateISO",
            },
        ),
    )
    client.mocks.create(mock)
    print("Created: SMTP welcome email mock")


def smtp_basic(client: MockartyClient) -> None:
    """Simple SMTP mock using the builder."""
    mock = (
        MockBuilder.smtp("test-smtp-server")
        .id("smtp-catch-all")
        .respond(200, body={
            "messageId": "$.fake.UUID",
            "accepted": True,
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: SMTP catch-all mock")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        kafka_topic_mock(client)
        kafka_with_conditions(client)
        kafka_with_output_routing(client)
        rabbitmq_queue_mock(client)
        rabbitmq_with_output(client)
        smtp_mock(client)
        smtp_basic(client)

        # Clean up
        mock_ids = [
            "kafka-order-events", "kafka-payment-requests", "kafka-order-router",
            "rabbitmq-notifications", "rabbitmq-order-processor",
            "smtp-welcome-email", "smtp-catch-all",
        ]
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        print("\nAll messaging example mocks cleaned up.")


if __name__ == "__main__":
    main()
