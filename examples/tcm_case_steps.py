"""Create a manual case, read/edit its steps, and save an idempotent version.

From the SDK repository root: python -m examples.tcm_case_steps
Set MOCKARTY_SERVER, MOCKARTY_API_KEY and MOCKARTY_NAMESPACE first.
"""
import os
from mockarty import MockartyClient


def main():
    with MockartyClient(base_url=os.environ["MOCKARTY_SERVER"], api_key=os.environ["MOCKARTY_API_KEY"], namespace=os.environ["MOCKARTY_NAMESPACE"]) as client:
        api = client.tcm
        case = api.create_case({"name": "Login smoke", "expectedResult": "Signed in", "steps": [{"stepUid": "login", "name": "Sign in", "mode": "manual", "executorType": "manual", "action": "Enter valid credentials", "expectedResult": "Home page"}]})
        version = api.get_case_version(case["id"], case["currentVersionId"])
        steps = version["steps"]
        steps[0]["expectedResult"] = "Dashboard displays the signed-in user"
        saved = api.save_case_steps(case["id"], steps, notes="Clarify expected result")
        repeated = api.save_case_steps(case["id"], steps, notes="Clarify expected result")
        if repeated["id"] != saved["id"] or not repeated.get("dedupSkipped"):
            raise RuntimeError("unchanged save did not return the same version")
        print(f"Case {case['id']} version {saved['version']}; unchanged save deduplicated")


if __name__ == "__main__":
    main()
