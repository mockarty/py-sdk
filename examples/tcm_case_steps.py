"""Create a manual case, read/edit its steps, and save an idempotent version.

From the SDK repository root: python -m examples.tcm_case_steps
Set MOCKARTY_SERVER, MOCKARTY_API_KEY and MOCKARTY_NAMESPACE first.
"""
import os
import base64
from mockarty import MockartyClient


def main():
    with MockartyClient(base_url=os.environ["MOCKARTY_SERVER"], api_key=os.environ["MOCKARTY_API_KEY"], namespace=os.environ["MOCKARTY_NAMESPACE"]) as client:
        api = client.tcm
        case_name = os.getenv("MOCKARTY_CASE_NAME", "Login smoke")
        case = api.create_case({"name": case_name, "externalId": os.getenv("MOCKARTY_SOURCE_CASE_ID", "sdk-demo:login-smoke"), "expectedResult": "Signed in", "customFields": [{"name": "Component", "value": "authentication"}], "steps": [{"stepUid": "login", "name": "Sign in", "mode": "manual", "executorType": "manual", "action": "Enter valid credentials", "expectedResult": "Home page"}]})
        if api.get_case(case["id"])["name"] != case_name:
            raise RuntimeError("case lookup changed the name")
        api.list_cases()
        version = api.get_case_version(case["id"], case["currentVersionId"])
        steps = version["steps"]
        # Edit the loaded dictionary to retain expectedAttachmentId and executorConfig.
        steps[0]["expectedResult"] = "Dashboard displays the signed-in user"
        saved = api.save_case_steps(case["id"], steps, notes="Clarify expected result")
        repeated = api.save_case_steps(case["id"], steps, notes="Clarify expected result")
        if repeated["id"] != saved["id"] or not repeated.get("dedupSkipped"):
            raise RuntimeError("unchanged save did not return the same version")
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
        filename = os.getenv("MOCKARTY_ATTACHMENT_NAME", "login.png")
        attachment = api.upload_attachment("tcm_case", case["id"], filename, png, media_type="image/png")
        media = api.list_attachments("tcm_case", case["id"])
        if not any(item["id"] == attachment["id"] and item["originalName"] == filename for item in media):
            raise RuntimeError("attachment name changed")
        if api.download_attachment(attachment["id"]) != png:
            raise RuntimeError("attachment bytes changed")
        run = api.run_case(case["id"], {"mode": "manual"})
        api.get_case_run(run["id"])
        print(f"Case {case['id']} version {saved['version']}, PNG {attachment['id']} ({len(png)} bytes), run {run['id']}; unchanged save deduplicated")


if __name__ == "__main__":
    main()
