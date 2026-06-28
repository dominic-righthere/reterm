"""Tests for animated SVG rendering."""

import re
import xml.dom.minidom as minidom

import pytest

from reterm.render.svg import (
    SvgWriter,
    _Cell,
    cells_from_plain,
    cells_from_styled_tuples,
)
from reterm.render.themes import DRACULA


def _writer() -> SvgWriter:
    return SvgWriter("out.svg", DRACULA, cols=12, rows=2)


class TestSvgWriter:
    def test_wellformed_with_frames_and_keyframes(self):
        w = _writer()
        w.add_frame([[_Cell("h"), _Cell("i")]], (0, 2), 100)
        w.add_frame([[_Cell("y"), _Cell("o")]], (0, 2), 100)
        svg = w.to_svg()
        minidom.parseString(svg)  # raises on malformed XML
        assert w.frame_count() == 2
        assert svg.count('<g class="f') == 2
        assert svg.count("@keyframes") == 2
        assert "step-end" in svg and "infinite" in svg

    def test_dedupes_consecutive_identical_frames(self):
        w = _writer()
        w.add_frame([[_Cell("a")]], (0, 1), 100)
        w.add_frame([[_Cell("a")]], (0, 1), 150)  # identical -> merged
        w.add_frame([[_Cell("b")]], (0, 1), 100)
        assert w.frame_count() == 2

    def test_resolves_named_and_hex_colors(self):
        w = _writer()
        w.add_frame([[_Cell("x", fg="green"), _Cell("y", fg="#abcdef")]], None, 100)
        svg = w.to_svg()
        assert DRACULA.green in svg  # pyte name -> theme hex
        assert "#abcdef" in svg  # hex passes through

    def test_bold_and_background_rendered(self):
        w = _writer()
        w.add_frame([[_Cell("Z", fg="red", bg="blue", bold=True)]], None, 100)
        svg = w.to_svg()
        assert 'font-weight="bold"' in svg
        assert "<rect" in svg and DRACULA.blue in svg  # bg run rect

    def test_keyframes_span_full_timeline(self):
        w = _writer()
        for i in range(4):
            w.add_frame([[_Cell(str(i))]], (0, 1), 100)
        svg = w.to_svg()
        # First frame is visible from 0%; last frame group is the static fallback.
        assert "0%{opacity:1}" in svg
        assert re.search(r'<g class="f3" opacity="1"', svg)
        assert re.search(r'<g class="f0" opacity="0"', svg)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            _writer().to_svg()

    def test_idle_cap_clamps_accumulated_static_hold(self):
        # A long static stretch is captured as many identical frames that merge;
        # the cap clamps the accumulated hold so dead air doesn't drag the loop.
        capped = SvgWriter("o.svg", DRACULA, cols=4, rows=1, max_frame_ms=2000)
        uncapped = SvgWriter("o.svg", DRACULA, cols=4, rows=1)
        for _ in range(50):  # 50 * 100ms = 5000ms of identical frames
            capped.add_frame([[_Cell("a")]], (0, 1), 100)
            uncapped.add_frame([[_Cell("a")]], (0, 1), 100)
        assert capped.frame_count() == 1 and uncapped.frame_count() == 1
        assert capped._frames[0][2] == 2000  # clamped
        assert uncapped._frames[0][2] == 5000  # full


class TestGifIdleCap:
    def test_cap_clamps_durations(self):
        from reterm.render.gif import GIFWriter

        assert GIFWriter("x.gif", max_frame_ms=2000)._cap([100, 5000, 1500]) == [100, 2000, 1500]
        assert GIFWriter("x.gif")._cap([5000]) == [5000]  # no cap -> unchanged

    def test_xml_escaping(self):
        w = _writer()
        w.add_frame([[_Cell("<"), _Cell("&"), _Cell(">")]], None, 100)
        svg = w.to_svg()
        assert "&lt;" in svg and "&amp;" in svg and "&gt;" in svg


class TestCellConverters:
    def test_from_styled_tuples(self):
        rows = cells_from_styled_tuples(
            [[("a", {"fg": "red", "bold": True, "underscore": True}), ("b", {})]]
        )
        assert rows[0][0].char == "a"
        assert rows[0][0].fg == "red"
        assert rows[0][0].bold and rows[0][0].underline
        assert rows[0][1].char == "b" and not rows[0][1].bold

    def test_from_plain(self):
        rows = cells_from_plain(["hi"])
        assert [c.char for c in rows[0]] == ["h", "i"]
        assert rows[0][0].fg is None
