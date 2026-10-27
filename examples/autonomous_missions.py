"""Submit and supervise one bounded goal-first autonomous mission."""

import os
from mockarty import (
    MissionAnswerRequest,
    MissionCancelRequest,
    MissionRevisionReference,
    MissionStartRequest,
    MockartyClient,
)


with MockartyClient(
    base_url=os.environ.get("MOCKARTY_BASE_URL"),
    api_key=os.environ.get("MOCKARTY_API_KEY"),
    namespace=os.environ.get("MOCKARTY_NAMESPACE", "sandbox"),
) as client:
    if answer := os.environ.get("MOCKARTY_EXAMPLE_ANSWER"):
        mission_id = os.environ["MOCKARTY_ANSWER_MISSION_ID"]
        retry_key = os.environ["MOCKARTY_ANSWER_IDEMPOTENCY_KEY"]
        if not retry_key.strip():
            raise ValueError("Use a nonempty retry key unique per answered question; reuse it on retry")
        # Capture these from data.question the user actually answered. Never
        # fetch a newer round to fill missing identity when retrying.
        if question_id := os.environ.get("MOCKARTY_QUESTION_ID"):
            answer_request = MissionAnswerRequest(
                question_id=question_id, revision=int(os.environ["MOCKARTY_QUESTION_REVISION"]),
                generation=int(os.environ.get("MOCKARTY_QUESTION_GENERATION", "0")),
                text=answer, idempotency_key=retry_key,
                # Choice/entity schemas instead use selected=[...] and entity={...}.
            )
        else:
            # Compatibility for engines that still expose freeform controls.
            answer_request = MissionAnswerRequest(answer=answer, idempotency_key=retry_key)
        answered = client.autonomous_missions.answer(mission_id, answer_request)
        print("answer receipt:", answered.control.id, answered.control.outcome)
        raise SystemExit(0)
    if archive_mission_id := os.environ.get("MOCKARTY_ARCHIVE_MISSION_ID"):
        archive = client.autonomous_missions.export_archive(archive_mission_id)
        restored = client.autonomous_missions.restore_archive(archive)
        print("archive:", archive.digest, "mission:", restored.id, "created:", restored.created)
    product_id = os.environ.get("MOCKARTY_PRODUCT_ID", "")
    settings = client.autonomous_missions.get_effective_settings(product_id=product_id)
    request = MissionStartRequest(
        goal="Take the checkout release to production quality and provide evidence",
        product_id=product_id,
        autonomy=os.environ.get("MOCKARTY_EXAMPLE_AUTONOMY", "auto"),
        budget_tokens_total=100_000,
        expected_settings_digest=settings.settings_digest,
    )
    # full preapproves testing of this declared product; chaos and paid effects
    # still need approval. Select it explicitly through the environment above.
    if target_url := os.environ.get("MOCKARTY_PRODUCT_URL"):
        request.data = {"contextRefs": [{"kind": "product_url", "value": target_url}]}
    if target_digest := os.environ.get("MOCKARTY_TARGET_DIGEST"):
        request.targets = [MissionRevisionReference(
            kind="repo",
            id=os.environ["MOCKARTY_TARGET_ID"],
            revision=int(os.environ["MOCKARTY_TARGET_REVISION"]),
            digest=target_digest,
        )]
    started = client.autonomous_missions.start(request)
    print("mission:", started.mission.id, started.mission.status, "created:", started.created)
    if os.environ.get("MOCKARTY_EXAMPLE_CANCEL") == "1":
        cancelled = client.autonomous_missions.cancel(
            started.mission.id,
            MissionCancelRequest(
                reason="example run no longer needed",
                idempotency_key="autonomous-missions-example-cancel",
            ),
        )
        print("cancel receipt:", cancelled.control.id, cancelled.control.outcome, cancelled.control.reason)
        for binding in cancelled.execution_bindings:
            print("child:", binding.external_id, binding.kind, binding.state)
