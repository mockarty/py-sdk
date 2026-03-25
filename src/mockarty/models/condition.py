# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Condition and assertion models matching Mockarty server API."""

from __future__ import annotations

import sys
from typing import Any, Optional

from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """Backport of StrEnum for Python < 3.11."""

        pass


class AssertAction(StrEnum):
    """Assertion actions supported by Mockarty condition matching."""

    EQUALS = "equals"
    CONTAINS = "contains"
    NOT_EQUALS = "not_equals"
    NOT_CONTAINS = "not_contains"
    ANY = "any"
    NOT_EMPTY = "notEmpty"
    EMPTY = "empty"
    MATCHES = "matches"


class Condition(BaseModel):
    """A single condition for matching incoming requests.

    Conditions evaluate a value extracted via ``path`` (JsonPath) against the
    expected ``value`` using the chosen ``assert_action``.
    """

    path: Optional[str] = Field(None, description="JsonPath to value in request body")
    assert_action: Optional[AssertAction] = Field(None, alias="assertAction")
    value: Optional[Any] = None
    value_from_file: Optional[str] = Field(None, alias="valueFromFile")
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")
    decode: Optional[str] = None

    model_config = {"populate_by_name": True}
