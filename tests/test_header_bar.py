"""Tests for the HeaderBar component."""

from __future__ import annotations

import sys
from types import ModuleType

# Save the real flet module so we can restore it after importing header_bar
# with our stub.  This prevents pollution of sys.modules for later test files.
_real_flet = sys.modules.get("flet")

# Stub flet before importing header_bar so tests run without the flet package.
_ft = ModuleType("flet")


class _FakeText:
    def __init__(self, value="", **kwargs):
        self.value = value
        self.size = kwargs.get("size")
        self.weight = kwargs.get("weight")
        self.opacity = kwargs.get("opacity")


class _FakeRow:
    def __init__(self, controls=None, **kwargs):
        self.controls = controls or []
        self.alignment = kwargs.get("alignment")
        self.vertical_alignment = kwargs.get("vertical_alignment")


class _FakeBlur:
    def __init__(self, sigma_x=0, sigma_y=0):
        self.sigma_x = sigma_x
        self.sigma_y = sigma_y


class _FakeContainer:
    def __init__(self, **kwargs):
        self.content = kwargs.get("content")
        self.bgcolor = kwargs.get("bgcolor")
        self.blur = kwargs.get("blur")
        self.padding = kwargs.get("padding")


class _FakePadding:
    @staticmethod
    def symmetric(horizontal=0, vertical=0):
        return {"horizontal": horizontal, "vertical": vertical}


class _FakeColors:
    @staticmethod
    def with_opacity(opacity, color):
        return f"{color}@{opacity}"


class _FakeFontWeight:
    BOLD = "bold"


class _FakeMainAxisAlignment:
    SPACE_BETWEEN = "spaceBetween"


class _FakeCrossAxisAlignment:
    CENTER = "center"


_ft.Text = _FakeText
_ft.Row = _FakeRow
_ft.Blur = _FakeBlur
_ft.Container = _FakeContainer
_ft.padding = _FakePadding()
_ft.Colors = _FakeColors()
_ft.FontWeight = _FakeFontWeight()
_ft.MainAxisAlignment = _FakeMainAxisAlignment()
_ft.CrossAxisAlignment = _FakeCrossAxisAlignment()
sys.modules["flet"] = _ft

from dc_shiftmaster_web.components.header_bar import build_header_bar  # noqa: E402

# Restore the real flet module so other test files are not affected.
if _real_flet is not None:
    sys.modules["flet"] = _real_flet
else:
    del sys.modules["flet"]


class TestBuildHeaderBar:
    """Unit tests for build_header_bar."""

    def test_returns_container(self):
        result = build_header_bar(2025, "ATL68")
        assert isinstance(result, _FakeContainer)

    def test_has_blur_effect(self):
        result = build_header_bar(2025, "ATL68")
        assert isinstance(result.blur, _FakeBlur)
        assert result.blur.sigma_x == 10
        assert result.blur.sigma_y == 10

    def test_semi_transparent_background(self):
        result = build_header_bar(2025, "ATL68")
        assert result.bgcolor is not None
        assert "#1E293B" in result.bgcolor
        assert "0.8" in result.bgcolor

    def test_contains_app_title(self):
        result = build_header_bar(2025, "ATL68")
        row = result.content
        assert isinstance(row, _FakeRow)
        title_text = row.controls[0]
        assert isinstance(title_text, _FakeText)
        assert title_text.value == "DC-ShiftMaster Pro"
        assert title_text.weight == "bold"

    def test_contains_region_and_year(self):
        result = build_header_bar(2025, "ATL68")
        row = result.content
        context_text = row.controls[1]
        assert isinstance(context_text, _FakeText)
        assert "ATL68" in context_text.value
        assert "2025" in context_text.value

    def test_empty_region_shows_dash(self):
        result = build_header_bar(2025, "")
        row = result.content
        context_text = row.controls[1]
        assert "—" in context_text.value
        assert "2025" in context_text.value

    def test_padding_applied(self):
        result = build_header_bar(2025, "ATL68")
        assert result.padding is not None
        assert result.padding["horizontal"] == 20
        assert result.padding["vertical"] == 10

    def test_context_text_has_reduced_opacity(self):
        result = build_header_bar(2025, "ATL68")
        context_text = result.content.controls[1]
        assert context_text.opacity == 0.7
