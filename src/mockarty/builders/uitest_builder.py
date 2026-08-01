# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Fluent builder for UI tests (recorded browser/mobile flows).

A ``UITest`` reconstructs the server's ``RecordedAction[]`` wire shape, so a
flow authored here — or generated from a Chrome-extension / companion recording
via ``mockarty-cli ui export --lang python`` — round-trips through
``POST /api/v1/ui-tests`` and runs on the platform's browser-runner / companion.
No Playwright/Appium toolchain lives in the SDK; the SDK orchestrates execution
on the platform and the result flows to TCM, unified with API/perf tests.
"""

from __future__ import annotations

import json
from typing import Any, Optional


class UITest:
    """Fluent UI-test builder.

    >>> ui = (UITest("checkout")
    ...       .navigate("https://shop.example.com")
    ...       .click("[data-testid=cart]")
    ...       .fill("#coupon", "SAVE10").press("#coupon", "Enter")
    ...       .assert_text(".total", "$90.00")
    ...       .assert_visible(".confirmation")
    ...       .screenshot())
    """

    def __init__(self, name: str, platform: str = "web") -> None:
        self._name = name
        self._platform = platform
        self._start_url: Optional[str] = None
        self._actions: list[dict[str, Any]] = []

    # -- config --------------------------------------------------------------

    def platform(self, p: str) -> "UITest":
        self._platform = p
        return self

    def start_url(self, url: str) -> "UITest":
        self._start_url = url
        return self

    def _add(self, action: dict[str, Any]) -> "UITest":
        self._actions.append({k: v for k, v in action.items() if v not in (None, "", {})})
        return self

    def selector_kind(self, kind: str) -> "UITest":
        """Override the locator strategy of the last-added action
        (css | testid | role | text | xpath). Emitted by codegen for fidelity."""
        if self._actions:
            self._actions[-1]["selectorKind"] = kind
        return self

    def extra(self, key: str, value: str) -> "UITest":
        if self._actions:
            self._actions[-1].setdefault("extras", {})[key] = value
        return self

    # -- navigation ----------------------------------------------------------

    def navigate(self, url: str) -> "UITest":
        return self._add({"type": "navigate", "value": url})

    def go_back(self) -> "UITest":
        return self._add({"type": "goBack"})

    def go_forward(self) -> "UITest":
        return self._add({"type": "goForward"})

    def reload(self) -> "UITest":
        return self._add({"type": "reload"})

    # -- interactions --------------------------------------------------------

    def click(self, selector: str) -> "UITest":
        return self._add({"type": "click", "selector": selector})

    def double_click(self, selector: str) -> "UITest":
        return self._add({"type": "dblclick", "selector": selector})

    def right_click(self, selector: str) -> "UITest":
        return self._add({"type": "rightclick", "selector": selector})

    def hover(self, selector: str) -> "UITest":
        return self._add({"type": "hover", "selector": selector})

    def focus(self, selector: str) -> "UITest":
        return self._add({"type": "focus", "selector": selector})

    def check(self, selector: str) -> "UITest":
        return self._add({"type": "check", "selector": selector})

    def uncheck(self, selector: str) -> "UITest":
        return self._add({"type": "uncheck", "selector": selector})

    def clear(self, selector: str) -> "UITest":
        return self._add({"type": "clear", "selector": selector})

    def scroll_into_view(self, selector: str) -> "UITest":
        return self._add({"type": "scrollIntoView", "selector": selector})

    def fill(self, selector: str, value: str) -> "UITest":
        return self._add({"type": "fill", "selector": selector, "value": value})

    def type(self, selector: str, value: str) -> "UITest":
        return self._add({"type": "type", "selector": selector, "value": value})

    def press(self, selector: str, key: str) -> "UITest":
        return self._add({"type": "press", "selector": selector, "value": key})

    def select(self, selector: str, value: str) -> "UITest":
        return self._add({"type": "select", "selector": selector, "value": value})

    def upload(self, selector: str, path: str) -> "UITest":
        return self._add({"type": "setInputFiles", "selector": selector, "value": path})

    def drag_and_drop(self, selector: str, target_selector: str) -> "UITest":
        return self._add({"type": "dragAndDrop", "selector": selector,
                          "extras": {"targetSelector": target_selector}})

    # -- assertions ----------------------------------------------------------

    def assert_visible(self, selector: str) -> "UITest":
        return self._add({"type": "assertVisible", "selector": selector})

    def assert_hidden(self, selector: str) -> "UITest":
        return self._add({"type": "assertHidden", "selector": selector})

    def assert_enabled(self, selector: str) -> "UITest":
        return self._add({"type": "assertEnabled", "selector": selector})

    def assert_disabled(self, selector: str) -> "UITest":
        return self._add({"type": "assertDisabled", "selector": selector})

    def assert_checked(self, selector: str) -> "UITest":
        return self._add({"type": "assertChecked", "selector": selector})

    def assert_text(self, selector: str, text: str) -> "UITest":
        return self._add({"type": "assertText", "selector": selector, "value": text})

    def assert_value(self, selector: str, value: str) -> "UITest":
        return self._add({"type": "assertValue", "selector": selector, "value": value})

    def assert_count(self, selector: str, n: int) -> "UITest":
        return self._add({"type": "assertCount", "selector": selector, "value": str(n)})

    def assert_attribute(self, selector: str, attr: str, value: str) -> "UITest":
        return self._add({"type": "assertAttribute", "selector": selector, "value": value,
                          "extras": {"attr": attr}})

    def assert_url(self, substr: str) -> "UITest":
        return self._add({"type": "assertURL", "value": substr})

    def assert_title(self, substr: str) -> "UITest":
        return self._add({"type": "assertTitle", "value": substr})

    # -- misc ----------------------------------------------------------------

    def wait_for(self, selector: str) -> "UITest":
        return self._add({"type": "waitFor", "selector": selector})

    def screenshot(self) -> "UITest":
        return self._add({"type": "screenshot"})

    def visual_check(self, selector: str) -> "UITest":
        return self._add({"type": "visualCheck", "selector": selector})

    def a11y_check(self) -> "UITest":
        return self._add({"type": "a11yCheck"})

    def action(self, action_type: str, selector: str = "", value: str = "") -> "UITest":
        """Escape hatch for any action type not covered by a typed helper."""
        return self._add({"type": action_type, "selector": selector, "value": value})

    # -- output --------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    def actions(self) -> list[dict[str, Any]]:
        return list(self._actions)

    def to_dict(self) -> dict[str, Any]:
        start = self._start_url
        if not start:
            for a in self._actions:
                if a.get("type") == "navigate" and a.get("value"):
                    start = a["value"]
                    break
        return {"name": self._name, "platform": self._platform,
                "startUrl": start or "", "actions": self._actions}

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
