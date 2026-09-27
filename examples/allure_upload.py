"""Upload Allure result JSON, recursive steps and small media.

Missing files fail preflight. Limits: 256 KiB/file, 1 MiB and 32 unique files
per result, 32 MiB/batch. Container fixtures are not imported by this helper.
Run: python examples/allure_upload.py ./allure-results
"""
import os
import sys
from mockarty.client import MockartyClient


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: allure_upload.py <allure-results-directory>")
    with MockartyClient(base_url=os.environ["MOCKARTY_SERVER"],
                        api_key=os.environ["MOCKARTY_API_KEY"],
                        namespace=os.environ["MOCKARTY_NAMESPACE"]) as client:
        rows = client.external_runs.upload_allure_dir(sys.argv[1], on_error="raise")
        print(f"Uploaded {len(rows)} results")


if __name__ == "__main__":
    main()
