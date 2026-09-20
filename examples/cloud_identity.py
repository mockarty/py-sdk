import os

from mockarty import MockartyClient

with MockartyClient(base_url=os.environ["MOCKARTY_BASE_URL"], api_key=os.environ["MOCKARTY_API_KEY"]) as client:
    for identity in client.cloud_identity.list():
        print(identity["provider"])
    # Use a Cloud cabinet session. Two distinct mailbox proofs are required;
    # setting a password alone never completes a sign-in email change.
    if new_email := os.environ.get("MOCKARTY_NEW_EMAIL"):
        print(client.cloud_identity.request_email_change(new_email)["stage"])
