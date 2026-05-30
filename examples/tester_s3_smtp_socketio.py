"""Author one autotest that exercises S3, SMTP and Socket.IO endpoints
through the Mockarty SDK Tester — the same way you'd test HTTP / gRPC /
Kafka.

Point it at a Mockarty testbackend (cmd/testbackend) or any
S3-compatible / SMTP / Socket.IO server::

    # from the main repo:
    go run ./cmd/testbackend &
    S3_ENDPOINT=http://localhost:18770/s3 \\
    SMTP_HOST=localhost SMTP_PORT=18772 \\
    SOCKETIO_URL=http://localhost:18770 \\
      python examples/tester_s3_smtp_socketio.py

Socket.IO requires the ``protocols`` extra: ``pip install 'mockarty[protocols]'``.
"""

import os
import sys
import time

from mockarty.protocols import s3 as s3proto
from mockarty.protocols import smtp as smtpproto
from mockarty.tester import Tester


def main() -> int:
    s3_endpoint = os.getenv("S3_ENDPOINT", "http://localhost:18770/s3")
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "18772"))
    socket_url = os.getenv("SOCKETIO_URL", "http://localhost:18770")

    t = Tester()

    # ── S3: put → get → list → delete ─────────────────────────────────
    s3cli = s3proto.Client(s3_endpoint)
    key = f"report-{time.strftime('%H%M%S')}.csv"
    (t.s3(s3cli).put("mockarty-test", key)
        .body("region,sales\neu,42\n").content_type("text/csv").meta("owner", "finance")
        .expect_ok().expect_status(200).extract_etag("etag"))
    (t.s3(s3cli).get("mockarty-test", key)
        .expect_ok().expect_content_type("text/csv")
        .expect_body_contains("eu,42").expect_meta("owner", "finance"))
    t.s3(s3cli).list("mockarty-test").expect_key(key)
    t.s3(s3cli).delete("mockarty-test", key).expect_ok().expect_status(204)

    # ── SMTP: send an authenticated mail ──────────────────────────────
    mail = smtpproto.Client(smtp_host, smtp_port, username="user", password="pass")
    (t.smtp(mail).send("billing@corp", "customer@corp")
        .subject("Your invoice").body("Please find your invoice attached.")
        .expect_accepted())

    # ── Socket.IO: connect → emit → assert echoed events ──────────────
    (t.socketio(socket_url).connect()
        .emit("greet", "World").collect(2.0)
        .expect_connected()
        .expect_event("greeting")
        .expect_event_json_path("greeting", "$.msg", "hello World"))

    t.finish()

    if t.ok():
        print(f"PASS — {len(t.report())} steps")
        return 0
    print("FAIL:")
    for e in t.errors():
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
