"""List every joined or owned Mockarty Cloud Space explicitly."""

import os

from mockarty import MockartyClient


with MockartyClient(
    base_url=os.environ["MOCKARTY_BASE_URL"],
    api_key=os.environ["MOCKARTY_API_KEY"],
) as client:
    spaces = client.cloud_spaces.list(limit=25)["items"]
    for space in spaces:
        usage = space["usage"]
        print(
            space["id"],
            space["name"],
            f"role={space['role']}",
            f"members={usage['accepted_humans']}",
            f"pending={usage['pending_invites']}",
        )
    if spaces:
        selected = client.cloud_spaces.get(spaces[0]["id"])["space"]
        # Account owners can inspect the Team-wide seat count for this Space.
        if selected.get("owned"):
            organization = client.cloud_spaces.organization(selected["id"])["organization"]
            print(f"account={organization['account_id']} occupied={organization['seats_used']}/{organization['seats_total']}")
            team_invite_id = os.getenv("MOCKARTY_TEAM_INVITE_ID")
            if team_invite_id:
                client.cloud_spaces.revoke_team_invite(
                    selected["id"], team_invite_id, os.environ["MOCKARTY_IDEMPOTENCY_KEY"]
                )
                print("Team invitation revoked")
        members = client.cloud_spaces.list_members(selected["id"], limit=25)["items"]
        invites = client.cloud_spaces.list_invites(selected["id"], limit=25)["items"]
        print(f"selected={selected['id']} members={len(members)} invites={len(invites)}")

        invite_email = os.getenv("MOCKARTY_INVITE_EMAIL")
        if invite_email:
            key = os.environ["MOCKARTY_IDEMPOTENCY_KEY"]
            etag = f'"space-{selected["id"]}-r{selected["revision"]}"'
            created = client.cloud_spaces.create_invite(
                selected["id"], invite_email, "viewer", etag, key
            )
            print(
                f"invite={created['invite']['id']} token={created['invite']['token']} "
                f"next_revision={created['revision']}"
            )

    invite_token = os.getenv("MOCKARTY_INVITE_TOKEN")
    if invite_token:
        preview = client.cloud_spaces.preview_invite(invite_token)
        accepted = client.cloud_spaces.accept_invite(
            invite_token, preview["etag"], os.environ["MOCKARTY_IDEMPOTENCY_KEY"]
        )
        print(f"accepted_space={accepted['space_id']} role={accepted['role']}")
