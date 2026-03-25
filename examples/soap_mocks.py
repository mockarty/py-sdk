"""SOAP mock examples.

Demonstrates:
  - SOAP service/method mock
  - SOAP fault responses
"""

from mockarty import (
    ContentResponse,
    Mock,
    MockBuilder,
    MockartyClient,
    SoapRequestContext,
)
from mockarty.models.mock import SOAPFault

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def soap_service_mock(client: MockartyClient) -> None:
    """Mock a SOAP service method: WeatherService.GetForecast."""
    mock = (
        MockBuilder.soap("WeatherService", "GetForecast")
        .id("soap-weather-forecast")
        .respond(200, body={
            "GetForecastResponse": {
                "city": "$.req.city",
                "temperature": 22,
                "unit": "celsius",
                "condition": "sunny",
                "forecast": [
                    {"day": "Monday", "high": 24, "low": 18, "condition": "sunny"},
                    {"day": "Tuesday", "high": 21, "low": 16, "condition": "cloudy"},
                    {"day": "Wednesday", "high": 19, "low": 14, "condition": "rain"},
                ],
            }
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: SOAP WeatherService/GetForecast")


def soap_with_conditions(client: MockartyClient) -> None:
    """SOAP mock with request body conditions."""
    from mockarty import AssertAction

    mock = (
        MockBuilder.soap("PaymentService", "ProcessPayment")
        .id("soap-process-payment")
        .condition("amount", AssertAction.NOT_EMPTY)
        .condition("currency", AssertAction.EQUALS, "USD")
        .respond(200, body={
            "ProcessPaymentResponse": {
                "transactionId": "$.fake.UUID",
                "status": "SUCCESS",
                "amount": "$.req.amount",
                "currency": "USD",
                "processedAt": "$.fake.DateISO",
            }
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: SOAP PaymentService/ProcessPayment (with conditions)")


def soap_fault_response(client: MockartyClient) -> None:
    """Return a SOAP fault (error) response.

    Uses the SOAPFault model to create a spec-compliant SOAP 1.1 fault.
    """
    mock = Mock(
        id="soap-auth-fault",
        soap=SoapRequestContext(
            service="AccountService",
            method="GetAccountDetails",
        ),
        response=ContentResponse(
            status_code=500,
            soap_fault=SOAPFault(
                fault_code="soap:Client",
                fault_string="Authentication required",
                fault_actor="http://example.com/AccountService",
                detail="<detail><errorCode>AUTH_001</errorCode>"
                       "<message>Invalid or expired token</message></detail>",
                http_status=401,
            ),
        ),
    )
    client.mocks.create(mock)
    print("Created: SOAP AccountService/GetAccountDetails (fault)")


def soap_server_fault(client: MockartyClient) -> None:
    """Simulate a SOAP server-side fault."""
    mock = Mock(
        id="soap-server-fault",
        soap=SoapRequestContext(
            service="InventoryService",
            method="CheckStock",
        ),
        response=ContentResponse(
            status_code=500,
            soap_fault=SOAPFault(
                fault_code="soap:Server",
                fault_string="Internal processing error",
                detail="<detail><errorCode>SRV_500</errorCode>"
                       "<message>Database connection timeout</message></detail>",
                http_status=500,
            ),
        ),
    )
    client.mocks.create(mock)
    print("Created: SOAP InventoryService/CheckStock (server fault)")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        soap_service_mock(client)
        soap_with_conditions(client)
        soap_fault_response(client)
        soap_server_fault(client)

        # Clean up
        mock_ids = [
            "soap-weather-forecast", "soap-process-payment",
            "soap-auth-fault", "soap-server-fault",
        ]
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        print("\nAll SOAP example mocks cleaned up.")


if __name__ == "__main__":
    main()
