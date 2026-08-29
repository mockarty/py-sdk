import os

from mockarty import MockartyClient


with MockartyClient(namespace=os.environ["MOCKARTY_NAMESPACE"]) as client:
    mission = client.coder_delivery.start_mission({
        "goal": "Deploy the accepted commit",
        "repoUrl": os.environ["CODER_REPO_URL"],
        "deployTarget": "staging",
    })
    print(mission["id"], mission["status"])
    if outcome := os.getenv("CODER_DEPLOY_RECONCILIATION"):
        mission = client.coder_delivery.reconcile_deploy(mission["id"], outcome)
        print("reconciled", mission.get("deployStopState"))
