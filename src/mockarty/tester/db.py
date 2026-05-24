# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""DB (SQL) facet — mirrors ``sdk/go-sdk/tester/db.go``.

SQLConn is a protocol the user implements (or adapts an existing DB
client to). The SDK ships ZERO database driver deps; the user plugs
in sqlite3 / psycopg2 / asyncpg / a test fake.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from .interpolate import interpolate
from .jsonpath import equal_json_scalar
from .tester import StepRecord, Tester


@dataclass
class DBExecResult:
    rows_affected: int = 0
    last_insert_id: int = 0


# DBRow = column name → value (any python type the driver returns).
DBRow = dict


class SQLConn(Protocol):
    def query(self, sql: str, *args) -> list[DBRow]: ...
    def exec(self, sql: str, *args) -> DBExecResult: ...


class DBFacet:
    def __init__(self, tester: Tester, conn: SQLConn) -> None:
        self._t = tester
        self._conn = conn

    def query(self, sql: str, *args) -> "DBStep":
        self._t._flush_pending()
        v = self._t._snapshot_vars()
        step = DBStep(
            self._t, self._conn, "query",
            sql=interpolate(sql, v),
            args=_interp_args(args, v),
        )
        self._t._set_pending(step)
        return step

    def exec(self, sql: str, *args) -> "DBStep":
        self._t._flush_pending()
        v = self._t._snapshot_vars()
        step = DBStep(
            self._t, self._conn, "exec",
            sql=interpolate(sql, v),
            args=_interp_args(args, v),
        )
        self._t._set_pending(step)
        return step


def _interp_args(args, vars_):
    return tuple(interpolate(a, vars_) if isinstance(a, str) else a for a in args)


class DBStep:
    def __init__(
        self, tester: Tester, conn: SQLConn, kind: str, sql: str, args: tuple,
    ) -> None:
        self._t = tester
        self._conn = conn
        self._kind = kind
        self._sql = sql
        self._args = args
        self._sent = False
        self._committed = False
        self._abort = False
        self._started_at = 0.0
        self._ended_at = 0.0
        self._rows: list[DBRow] = []
        self._result = DBExecResult()
        self._err: Optional[Exception] = None
        self._failures: list[str] = []

    def expect_ok(self) -> "DBStep":
        if not self._ensure_sent():
            return self
        if self._err is not None:
            self._fail(f"expect_ok: {self._err}")
        return self

    def expect_error(self) -> "DBStep":
        self._ensure_sent()
        if self._err is None:
            self._fail("expect_error: query succeeded")
        return self

    def expect_row_count(self, n: int) -> "DBStep":
        if not self._ensure_sent():
            return self
        if self._kind != "query":
            return self._fail("expect_row_count only valid after query()")
        if len(self._rows) != n:
            self._fail(f"expect_row_count: want {n}, got {len(self._rows)}")
        return self

    def expect_at_least_rows(self, n: int) -> "DBStep":
        if not self._ensure_sent():
            return self
        if self._kind != "query":
            return self._fail("expect_at_least_rows only valid after query()")
        if len(self._rows) < n:
            self._fail(f"expect_at_least_rows: want >={n}, got {len(self._rows)}")
        return self

    def expect_field(self, row: int, col: str, want: Any) -> "DBStep":
        if not self._ensure_sent():
            return self
        if row < 0 or row >= len(self._rows):
            return self._fail(
                f"expect_field[{row}.{col}]: row out of range (len={len(self._rows)})"
            )
        if col not in self._rows[row]:
            return self._fail(
                f"expect_field[{row}.{col}]: column not in result"
            )
        got = self._rows[row][col]
        if not equal_json_scalar(got, want):
            self._fail(f"expect_field[{row}.{col}]: want {want!r}, got {got!r}")
        return self

    def expect_column(self, col: str, want: Any) -> "DBStep":
        return self.expect_field(0, col, want)

    def expect_affected(self, n: int) -> "DBStep":
        if not self._ensure_sent():
            return self
        if self._kind != "exec":
            return self._fail("expect_affected only valid after exec()")
        if self._result.rows_affected != n:
            self._fail(f"expect_affected: want {n}, got {self._result.rows_affected}")
        return self

    def extract(self, row: int, col: str, name: str) -> "DBStep":
        if not self._ensure_sent():
            return self
        if row < 0 or row >= len(self._rows):
            return self._fail(
                f"extract[{row}.{col}]: row out of range (len={len(self._rows)})"
            )
        if col not in self._rows[row]:
            return self._fail(f"extract[{row}.{col}]: column not in result")
        v = self._rows[row][col]
        self._t.set_var(name, _stringify_db(v))
        return self

    def rows(self) -> list[DBRow]:
        self._ensure_sent()
        return [dict(r) for r in self._rows]

    def result(self) -> DBExecResult:
        self._ensure_sent()
        return self._result

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    def _fail(self, msg: str) -> "DBStep":
        self._failures.append(msg)
        return self

    def _ensure_sent(self) -> bool:
        if self._sent:
            return not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            return self._fail("skipped: fail-fast triggered by earlier step")._abort  # type: ignore
        self._started_at = time.time()
        try:
            if self._kind == "exec":
                self._result = self._conn.exec(self._sql, *self._args)
            else:
                self._rows = self._conn.query(self._sql, *self._args)
        except Exception as e:
            self._err = e
            self._ended_at = time.time()
            return True
        self._ended_at = time.time()
        return True

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        rec = StepRecord(
            protocol="sql",
            method=self._kind,
            name=f"sql {self._kind} {_sql_preview(self._sql)}",
            url=_sql_preview(self._sql),
            status_or_code=len(self._rows) if self._kind == "query" else self._result.rows_affected,
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)


def _sql_preview(q: str) -> str:
    q = " ".join(q.split())
    if len(q) > 80:
        return q[:77] + "..."
    return q


def _stringify_db(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)
    return json.dumps(v, default=str)
