"""Protocol clients for Mockarty's Python SDK.

This subpackage hosts thin clients for the protocols Mockarty supports
beyond plain HTTP: SOAP, GraphQL, Server-Sent Events, WebSocket, S3,
SMTP, Socket.IO. Each client is a CI-test-focused helper — it captures
every call as a :class:`mockarty.protocols.telemetry.Step` so a CI run's
TCM external report shows a per-operation timeline at the end of the
test.

The clients are deliberately small. They expose only the surface
useful from CI/CD scripts and tests — no admin / topology / message-
broker management surface. Air-gapped friendly: SOAP / GraphQL / SSE /
S3 ride on ``httpx`` (already a core dep); SMTP rides on the stdlib
``smtplib``; WebSocket / Socket.IO pull ``websockets`` through the
optional ``protocols`` extra.

Import paths::

    from mockarty.protocols import soap, graphql, sse, websocket
    from mockarty.protocols import s3, smtp, socketio
    from mockarty.protocols.telemetry import (
        Step, StepRecorder, NopRecorder, AccumulatingRecorder,
    )
"""

from .telemetry import (
    AccumulatingRecorder,
    NopRecorder,
    Step,
    StepRecorder,
    cap_preview,
    new_step_key,
)

__all__ = [
    "AccumulatingRecorder",
    "NopRecorder",
    "Step",
    "StepRecorder",
    "cap_preview",
    "new_step_key",
]
