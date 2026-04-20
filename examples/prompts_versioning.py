# Copyright (c) 2026 Mockarty. All rights reserved.
"""Prompts Storage — create, update, view history, rollback."""

from __future__ import annotations

from mockarty import MockartyClient


def main() -> None:
    with MockartyClient(api_key="your-api-key", namespace="sandbox") as client:
        p = client.prompts.create_prompt(
            name="tcm-step-summarizer",
            body="Summarize the following test step in one sentence: {{.step}}",
            model="claude-opus-4-7",
            tags=["tcm", "summary"],
        )
        print(f"[1] created {p['name']} v{p['version']}")

        try:
            client.prompts.update_prompt(
                p["id"], body="Summarize in ≤15 words: {{.step}}"
            )
            p = client.prompts.update_prompt(
                p["id"], body="One sentence summary, verb-first: {{.step}}"
            )
            print(f"[2] current v{p['version']}")

            versions = client.prompts.list_versions(p["id"])
            print(f"[3] history: {len(versions)} versions")

            rolled = client.prompts.rollback(p["id"], to_version=1)
            print(f"[4] rolled back; new v{rolled['version']}")
        finally:
            client.prompts.delete_prompt(p["id"])


if __name__ == "__main__":
    main()
