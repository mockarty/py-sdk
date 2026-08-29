import os

from mockarty import MockartyClient


with MockartyClient(namespace=os.getenv("MOCKARTY_NAMESPACE", "default")) as client:
    page = client.media_delivery.list_fenced("transcribe")
    print("fenced deliveries:", page["count"])
