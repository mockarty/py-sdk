"""List safe Cloud connector metadata; secret values are never returned."""

from mockarty import MockartyClient

with MockartyClient() as client:
    for connector in client.cloud_connectors.list():
        print(connector["key"], connector["revision"], connector["secret_configured"])
