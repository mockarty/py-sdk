# Copyright (c) 2026 Mockarty. All rights reserved.

"""Recycle Bin demo — list, restore, purge.

Environment:

    MOCKARTY_BASE_URL    — server URL (default http://localhost:5770)
    MOCKARTY_API_KEY     — API key
    MOCKARTY_NAMESPACE   — namespace to operate on
    MOCKARTY_CASCADE_IDS — (optional) comma-separated cascade group IDs to
                           restore, then purge. If unset, the script stops
                           after the read-only summary step.
"""

from __future__ import annotations

import os

from mockarty import (
    TRASH_PURGE_CONFIRMATION_PHRASE,
    MockartyClient,
    PurgeConfirmationError,
)


def main() -> None:
    ns = os.environ.get("MOCKARTY_NAMESPACE", "sandbox")
    with MockartyClient(namespace=ns) as client:
        # 1. Read-only overview.
        summary = client.trash.summary(ns)
        print(f"{ns} — {summary.total} items in Recycle Bin")
        for c in summary.counts:
            print(f"  {c.entity_type:18} {c.count}")

        page = client.trash.list_trash(ns, limit=10)
        for it in page.items:
            flag = "OK" if it.restore_available else "BLOCKED"
            print(
                f"  [{flag}] {it.entity_type} {it.name} ({it.id}) "
                f"closed_by={it.closed_by} cascade={it.cascade_group_id}"
            )

        ids_raw = os.environ.get("MOCKARTY_CASCADE_IDS", "").strip()
        if not ids_raw:
            return
        ids = [x.strip() for x in ids_raw.split(",") if x.strip()]

        # 2. Bulk restore.
        restored = client.trash.bulk_restore(
            ns, cascade_group_ids=ids, reason="demo restore"
        )
        print(
            f"\nRestored {len(restored.restored)} groups, "
            f"{len(restored.failed)} failed, {len(restored.not_found)} not found"
        )

        # 3. Bulk purge — IRREVERSIBLE, guarded by the confirmation phrase.
        try:
            purged = client.trash.bulk_purge(
                ns,
                cascade_group_ids=ids,
                confirmation=TRASH_PURGE_CONFIRMATION_PHRASE,
                reason="demo purge",
            )
        except PurgeConfirmationError as exc:
            print(f"refusing to purge: {exc}")
            return

        print(
            f"Purged {len(purged.purged)} groups "
            f"({sum(p.rows_deleted for p in purged.purged)} rows total)"
        )


if __name__ == "__main__":
    main()
