import os

from mockarty import MockartyClient


with MockartyClient(namespace=os.environ["MOCKARTY_NAMESPACE"]) as client:
    if os.getenv("MISSION_PRODUCT_ID"):
        # Text originals in one mission must total at most 64 KiB.
        material = client.coder_delivery.upload_mission_material(os.environ["MISSION_PRODUCT_ID"], "design.txt", b"Palette: navy and cream. Keep accessible contrast.", "text/plain")
        print("Use in POST /api/v1/missions artifacts:", material["reference"])
    mission = client.coder_delivery.start_mission({
        "goal": "Deploy the accepted commit",
        "repoUrl": os.environ["CODER_REPO_URL"],
        "deployTarget": "staging",
    })
    print(mission["id"], mission["status"])
    print("independent AQC receipts", len(mission.get("aqcEvidence", [])), "merge status", mission.get("mrMergeStatus"), "repair attempts", mission.get("deployRepairAttempts", 0))
    if os.getenv("CODER_ADD_GO_CHECK") == "1":
        mission = client.coder_delivery.add_to_mission(mission["id"], {
            "tasks": [{
                "prompt": "Run and fix the Go unit suite",
                "requiredChecks": [{"name": "Go unit tests", "args": ["go", "test", "./..."]}],
            }],
        })
    if outcome := os.getenv("CODER_DEPLOY_RECONCILIATION"):
        mission = client.coder_delivery.reconcile_deploy(mission["id"], outcome)
        print("reconciled", mission.get("deployStopState"))
    if os.getenv("CODER_OBSERVE") == "1":
        print("observability sources", len(client.coder_delivery.observability_sources().get("sources", [])))
