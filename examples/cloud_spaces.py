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
    team_audit_space_id = os.getenv("MOCKARTY_TEAM_AUDIT_SPACE_ID")
    if team_audit_space_id:
        audit = client.cloud_spaces.list_team_audit(
            team_audit_space_id, os.getenv("MOCKARTY_TEAM_AUDIT_BEFORE_ID", ""), limit=50
        )
        print(
            f"team={audit['team_id']} events={len(audit['records'])} "
            f"chain_ok={audit['chain_ok']} has_more={audit['has_more']} "
            f"next_before_id={audit['next_before_id']}"
        )
    if spaces:
        selected = client.cloud_spaces.get(spaces[0]["id"])["space"]
        # Account owners can inspect the Team-wide seat count for this Space.
        if selected.get("owned"):
            organization = client.cloud_spaces.organization(selected["id"])["organization"]
            print(f"account={organization['account_id']} occupied={organization['seats_used']}/{organization['seats_total']}")
            if organization["account_kind"] == "team":
                member_id = os.getenv("MOCKARTY_TEAM_REMOVE_MEMBER_ID")
                if member_id:
                    client.cloud_spaces.remove_team_member(
                        selected["id"], member_id, os.environ["MOCKARTY_TEAM_MEMBER_REMOVE_KEY"]
                    )
                    print("Team member removed")
                successor_id = os.getenv("MOCKARTY_TEAM_SUCCESSOR_ID")
                if successor_id:
                    client.cloud_spaces.transfer_team_owner(
                        selected["id"], successor_id, os.environ["MOCKARTY_TEAM_OWNER_TRANSFER_KEY"]
                    )
                    print("Team ownership transferred")
                team_space_name = os.getenv("MOCKARTY_TEAM_SPACE_NAME")
                if team_space_name:
                    created = client.cloud_spaces.create_team_space(
                        organization["account_id"], team_space_name, "team",
                        os.environ["MOCKARTY_TEAM_SPACE_KEY"],
                    )
                    print(f"created_team_space={created['space_id']}")
                team_email = os.getenv("MOCKARTY_TEAM_MEMBER_EMAIL")
                if team_email:
                    client.cloud_spaces.invite_team_member(
                        selected["id"], team_email, "member", os.environ["MOCKARTY_TEAM_INVITE_KEY"]
                    )
                    print("Team invitation queued")
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
