# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Wrap / Eventually / Parallel chain helpers.

Mirrors ``sdk/go-sdk/tester/ergonomics.go``.
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Callable, Optional

from .tester import Tester


def wrap(t: Tester, name: str, fn: Callable[[], None]) -> Tester:
    """Run ``fn`` inside a parent group named ``name``. Any chains fired
    from inside ``fn`` group under it in the report.

    Allure step nesting requires hooks into the pytest plugin; the SDK
    keeps the group purely in the in-memory report for now (the pytest
    plugin can read the step list and turn it into a nested Allure step).
    """
    t._flush_pending()
    # Mark the boundary by recording a synthetic group step.
    from .tester import StepRecord

    rec = StepRecord(
        protocol="group",
        method="wrap",
        name=name,
        started_at=time.time(),
    )
    try:
        fn()
    finally:
        t._flush_pending()
        rec.ended_at = time.time()
        t._record_step(rec)
    return t


def eventually(
    t: Tester,
    within: float,
    interval: float,
    fn: Callable[[], Optional[Exception]],
) -> bool:
    """Retry ``fn`` until it returns ``None`` (success) or ``within``
    seconds elapse. Intermediate failures are rolled back so only the
    final attempt's steps appear in the report. ``interval`` (seconds)
    defaults to 0.1 if non-positive.
    """
    if interval <= 0:
        interval = 0.1
    deadline = time.time() + within
    last_err: Optional[Exception] = None
    while True:
        t._flush_pending()
        with t._lock:
            step_bookmark = len(t._steps)
            err_bookmark = len(t._errs)
        err = fn()
        t._flush_pending()
        if err is None:
            with t._lock:
                t._errs = t._errs[:err_bookmark]
            return True
        last_err = err
        with t._lock:
            t._steps = t._steps[:step_bookmark]
            t._errs = t._errs[:err_bookmark]
        if time.time() > deadline:
            t._flush_pending()
            with t._lock:
                t._steps = t._steps[:step_bookmark]
                t._errs = t._errs[:err_bookmark]
            _ = fn()
            t._flush_pending()
            if last_err is not None:
                with t._lock:
                    t._errs.append(str(last_err))
            return False
        time.sleep(interval)


def parallel(t: Tester, *fns: Callable[[Tester], None]) -> Tester:
    """Run each fn in its own thread with a branch-local Tester that
    shares the parent's transport/baseURL/headers + var-store snapshot.
    Results merge back into the parent after all branches complete.
    """
    if not fns:
        return t
    t._flush_pending()
    results_steps: list[list] = [[] for _ in fns]
    results_errs: list[list] = [[] for _ in fns]
    threads: list[threading.Thread] = []
    for i, fn in enumerate(fns):

        def _worker(idx=i, f=fn):
            branch = _spawn_branch(t)
            try:
                f(branch)
            finally:
                branch._flush_pending()
                with branch._lock:
                    results_steps[idx] = list(branch._steps)
                    results_errs[idx] = list(branch._errs)

        th = threading.Thread(target=_worker)
        th.start()
        threads.append(th)
    for th in threads:
        th.join()
    with t._lock:
        for s in results_steps:
            t._steps.extend(s)
        for e in results_errs:
            t._errs.extend(e)
    return t


def _spawn_branch(t: Tester) -> Tester:
    """Make a child Tester that copies the parent's transport + var
    snapshot. Child writes do NOT propagate back to the parent's vars.
    """
    branch = Tester(
        base_url=t.base_url,
        http_client=t._http,  # share transport — httpx.Client is thread-safe
        default_headers=copy.copy(t._default_headers),
        fail_fast=t._fail_fast,
    )
    branch._owns_http = False
    with t._lock:
        branch._vars = dict(t._vars)
    return branch
