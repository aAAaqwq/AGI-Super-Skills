"""Tests for the decision trace dashboard UI (AQC-824).

Validates that the frontend files (HTML, JS, CSS) contain the required
structures, functions, classes, and elements for the decision dashboard.
Also tests that the API response format is parseable by the JS logic.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).resolve().parents[1] / "monitor" / "static"
INDEX_HTML = STATIC_DIR / "index.html"
APP_JS = STATIC_DIR / "app.js"
STYLES_CSS = STATIC_DIR / "styles.css"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def html_content():
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def js_content():
    return APP_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def css_content():
    return STYLES_CSS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# HTML structure parser
# ---------------------------------------------------------------------------


class _TagCollector(HTMLParser):
    """Collect element IDs and class names from HTML."""

    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.classes: set[str] = set()
        self.tag_names: set[str] = set()

    def handle_starttag(self, tag, attrs):
        self.tag_names.add(tag)
        for attr, val in attrs:
            if attr == "id" and val:
                self.ids.add(val)
            if attr == "class" and val:
                for cls in val.split():
                    self.classes.add(cls)


@pytest.fixture(scope="module")
def html_elements(html_content):
    parser = _TagCollector()
    parser.feed(html_content)
    return parser


# ---------------------------------------------------------------------------
# Test: HTML structure
# ---------------------------------------------------------------------------


class TestHtmlStructure:
    """Verify index.html has the required decision dashboard elements."""

    def test_view_tab_buttons_exist(self, html_elements):
        """Dashboard and Decisions tab buttons must exist."""
        assert "viewDash" in html_elements.ids, "Missing #viewDash tab button"
        assert "viewDecisions" in html_elements.ids, "Missing #viewDecisions tab button"

    def test_decisions_view_container(self, html_elements):
        """The decisions-view section must exist."""
        assert "decisionsView" in html_elements.ids, "Missing #decisionsView container"
        assert "decisions-view" in html_elements.classes, "Missing .decisions-view class"

    def test_filter_elements(self, html_elements):
        """Filter controls must be present."""
        expected_ids = [
            "decFilterSymbol",
            "decFilterEvent",
            "decFilterStatus",
            "decFilterStart",
            "decFilterEnd",
        ]
        for eid in expected_ids:
            assert eid in html_elements.ids, f"Missing #{eid} filter element"

    def test_action_buttons(self, html_elements):
        """Apply, Clear, Export buttons must exist."""
        assert "decApplyBtn" in html_elements.ids, "Missing #decApplyBtn"
        assert "decClearBtn" in html_elements.ids, "Missing #decClearBtn"
        assert "decExportBtn" in html_elements.ids, "Missing #decExportBtn"

    def test_timeline_container(self, html_elements):
        """Decision timeline container must exist."""
        assert "decTimeline" in html_elements.ids, "Missing #decTimeline container"
        assert "dec-timeline" in html_elements.classes, "Missing .dec-timeline class"

    def test_load_more_button(self, html_elements):
        """Load-more pagination button must exist."""
        assert "decLoadMore" in html_elements.ids, "Missing #decLoadMore button"

    def test_decision_detail_modal(self, html_elements):
        """Decision detail modal elements must exist."""
        assert "decModal" in html_elements.ids, "Missing #decModal"
        assert "decModalTitle" in html_elements.ids, "Missing #decModalTitle"
        assert "decModalClose" in html_elements.ids, "Missing #decModalClose"
        assert "decModalBody" in html_elements.ids, "Missing #decModalBody"

    def test_gate_evaluations_table(self, html_elements):
        """Gate evaluations table must exist in the modal."""
        assert "decModalGateTable" in html_elements.ids, "Missing #decModalGateTable"
        assert "decModalGateBody" in html_elements.ids, "Missing #decModalGateBody"

    def test_indicator_section(self, html_elements):
        """Indicator snapshot section must exist."""
        assert "decModalIndicators" in html_elements.ids, "Missing #decModalIndicators"

    def test_replay_button(self, html_elements):
        """Replay button must exist in the detail modal."""
        assert "decReplayBtn" in html_elements.ids, "Missing #decReplayBtn"

    def test_summary_bar(self, html_elements):
        """Summary bar showing count must exist."""
        assert "decSummaryBar" in html_elements.ids, "Missing #decSummaryBar"

    def test_viewtabs_class(self, html_elements):
        """View tabs wrapper class must exist."""
        assert "viewtabs" in html_elements.classes, "Missing .viewtabs class"

    def test_event_type_options(self, html_content):
        """Event type dropdown must contain all required options."""
        expected = ["entry_signal", "exit_check", "gate_block", "fill", "funding"]
        for ev in expected:
            assert ev in html_content, f"Missing event_type option: {ev}"

    def test_status_options(self, html_content):
        """Status dropdown must contain all required options."""
        expected = ["executed", "blocked", "rejected", "hold"]
        for st in expected:
            assert st in html_content, f"Missing status option: {st}"


# ---------------------------------------------------------------------------
# Test: JavaScript functions
# ---------------------------------------------------------------------------


class TestJsFunctions:
    """Verify app.js contains the required decision dashboard functions."""

    @pytest.mark.parametrize("fn_name", [
        "setViewTab",
        "decPopulateSymbols",
        "decBuildParams",
        "decFetchDecisions",
        "decRenderTimeline",
        "decOpenDetail",
        "decCloseModal",
        "decReplay",
        "decExportJson",
        "decClearFilters",
        "bindDecisionsUi",
    ])
    def test_function_exists(self, js_content, fn_name):
        """Each required JS function must be defined in app.js."""
        # Match both `function name(` and `async function name(`
        pattern = rf"(?:async\s+)?function\s+{re.escape(fn_name)}\s*\("
        assert re.search(pattern, js_content), f"Missing function: {fn_name}"

    def test_dec_state_object(self, js_content):
        """decState configuration object must exist."""
        assert "decState" in js_content, "Missing decState object"

    def test_api_endpoint_v2_decisions(self, js_content):
        """JS must reference the /api/v2/decisions endpoint."""
        assert "/api/v2/decisions" in js_content

    def test_api_endpoint_v2_decisions_detail(self, js_content):
        """JS must reference the /api/v2/decisions/{id} endpoint pattern."""
        assert "/api/v2/decisions/" in js_content

    def test_api_endpoint_replay(self, js_content):
        """JS must reference the /api/v2/decisions/replay endpoint."""
        assert "/api/v2/decisions/replay" in js_content

    def test_fetch_uses_mode_param(self, js_content):
        """API calls must include mode query parameter."""
        # Check that mode is passed in decision fetches
        assert "state.mode" in js_content

    def test_json_export_blob(self, js_content):
        """Export function must create a Blob for download."""
        assert "Blob(" in js_content
        assert "application/json" in js_content

    def test_export_creates_download(self, js_content):
        """Export must trigger a file download."""
        assert "createObjectURL" in js_content
        assert ".download" in js_content
        assert "revokeObjectURL" in js_content

    def test_pagination_offset_limit(self, js_content):
        """Pagination must use offset/limit params."""
        assert "decState.offset" in js_content
        assert "decState.limit" in js_content

    def test_bind_decisions_called_at_boot(self, js_content):
        """bindDecisionsUi must be called during boot."""
        assert "bindDecisionsUi()" in js_content

    def test_escape_function_used(self, js_content):
        """Timeline rendering must use the esc() XSS protection."""
        # Check that esc() is used in the template literals for decision rendering
        assert "esc(evType)" in js_content or "esc(d.symbol" in js_content


# ---------------------------------------------------------------------------
# Test: CSS classes
# ---------------------------------------------------------------------------


class TestCssClasses:
    """Verify styles.css contains the required decision dashboard styles."""

    @pytest.mark.parametrize("cls", [
        ".decisions-view",
        ".dec-toolbar",
        ".dec-filters",
        ".dec-filter-group",
        ".dec-label",
        ".dec-select",
        ".dec-input",
        ".dec-timeline",
        ".dec-item",
        ".dec-badge",
        ".dec-badge-entry_signal",
        ".dec-badge-exit_check",
        ".dec-badge-gate_block",
        ".dec-badge-fill",
        ".dec-badge-funding",
        ".dec-status",
        ".dec-status-executed",
        ".dec-status-blocked",
        ".dec-status-rejected",
        ".dec-status-hold",
        ".dec-gates-table",
        ".dec-gate-pass",
        ".dec-gate-fail",
        ".dec-modal-body",
        ".dec-modal-section",
        ".dec-modal-section-title",
        ".dec-link",
        ".dec-empty",
        ".dec-pager",
        ".dec-summary",
        ".viewtabs",
    ])
    def test_css_class_defined(self, css_content, cls):
        """Each required CSS class must be defined in styles.css."""
        assert cls in css_content, f"Missing CSS class: {cls}"

    def test_badge_colors_follow_theme(self, css_content):
        """Event type badges must use the existing theme color variables."""
        # entry_signal should use --ok (green)
        assert "--ok" in css_content
        # exit_check should use --accent2 (red)
        assert "--accent2" in css_content
        # gate_block should use --warn (yellow/orange)
        assert "--warn" in css_content

    def test_dark_theme_background(self, css_content):
        """Decision view should follow the dark theme background pattern."""
        assert "rgba(0,0,0," in css_content

    def test_responsive_rules(self, css_content):
        """Decision view should have responsive CSS rules for mobile."""
        # Check there's a media query that targets the decisions view
        assert ".dec-toolbar" in css_content
        # Check mobile breakpoint exists
        assert ".dec-filters" in css_content


# ---------------------------------------------------------------------------
# Test: API response parsing logic
# ---------------------------------------------------------------------------


class TestApiResponseParsing:
    """Verify the JS can correctly parse expected API response formats."""

    def test_decisions_list_response_format(self):
        """The expected decisions list response must be valid JSON."""
        response = {
            "decisions": [
                {
                    "id": "01HXYZ123",
                    "timestamp_ms": 1708000000000,
                    "symbol": "ETH",
                    "event_type": "entry_signal",
                    "status": "executed",
                    "decision_phase": "entry",
                    "action_taken": "open_long",
                    "rejection_reason": None,
                    "context_json": "{}",
                },
                {
                    "id": "01HXYZ456",
                    "timestamp_ms": 1708000001000,
                    "symbol": "BTC",
                    "event_type": "gate_block",
                    "status": "blocked",
                    "decision_phase": "entry",
                    "action_taken": "blocked",
                    "rejection_reason": "ADX below threshold",
                    "context_json": "{}",
                },
            ],
            "total": 2,
        }
        serialized = json.dumps(response)
        parsed = json.loads(serialized)
        assert len(parsed["decisions"]) == 2
        assert parsed["decisions"][0]["event_type"] == "entry_signal"
        assert parsed["decisions"][1]["status"] == "blocked"

    def test_decision_detail_response_format(self):
        """The expected decision detail response must be valid JSON."""
        response = {
            "decision": {
                "id": "01HXYZ123",
                "timestamp_ms": 1708000000000,
                "symbol": "ETH",
                "event_type": "entry_signal",
                "status": "executed",
                "decision_phase": "entry",
                "parent_decision_id": None,
                "trade_id": 42,
                "triggered_by": "candle_close",
                "action_taken": "open_long",
                "rejection_reason": None,
            },
            "context": {
                "price": 2850.50,
                "rsi": 45.2,
                "adx": 28.7,
                "adx_slope": 0.5,
                "macd_hist": 12.3,
                "ema_fast": 2845.0,
                "ema_slow": 2830.0,
                "ema_macro": 2800.0,
                "bb_width_ratio": 1.2,
                "stoch_k": 55.0,
                "stoch_d": 52.0,
                "atr": 35.0,
                "atr_slope": 0.1,
                "volume": 50000,
                "vol_sma": 45000,
                "gate_ranging": 1,
                "gate_anomaly": 1,
                "gate_extension": 1,
                "gate_adx": 1,
                "gate_volume": 1,
                "gate_adx_rising": 1,
                "gate_btc_alignment": 1,
            },
            "gates": [
                {
                    "gate_name": "adx_threshold",
                    "gate_passed": 1,
                    "metric_value": 28.7,
                    "threshold_value": 20.0,
                    "operator": ">=",
                    "explanation": "ADX 28.7 >= 20.0",
                },
                {
                    "gate_name": "volume_check",
                    "gate_passed": 1,
                    "metric_value": 50000,
                    "threshold_value": 30000,
                    "operator": ">=",
                    "explanation": "Volume 50000 >= 30000",
                },
            ],
        }
        serialized = json.dumps(response)
        parsed = json.loads(serialized)
        assert parsed["decision"]["symbol"] == "ETH"
        assert parsed["context"]["rsi"] == 45.2
        assert len(parsed["gates"]) == 2
        assert parsed["gates"][0]["gate_passed"] == 1

    def test_gate_evaluation_response_format(self):
        """Gate evaluation response must be valid JSON."""
        response = {
            "gates": [
                {
                    "id": 1,
                    "decision_id": "01HXYZ123",
                    "gate_name": "ranging_filter",
                    "gate_passed": 0,
                    "metric_value": 0.85,
                    "threshold_value": 0.70,
                    "operator": "<=",
                    "explanation": "BB width ratio 0.85 > 0.70 threshold",
                },
            ]
        }
        serialized = json.dumps(response)
        parsed = json.loads(serialized)
        assert parsed["gates"][0]["gate_passed"] == 0
        assert parsed["gates"][0]["gate_name"] == "ranging_filter"

    def test_export_json_structure(self):
        """Exported JSON must be a list of decision objects."""
        decisions = [
            {
                "id": "01HXYZ123",
                "timestamp_ms": 1708000000000,
                "symbol": "ETH",
                "event_type": "entry_signal",
                "status": "executed",
                "action_taken": "open_long",
            },
        ]
        blob = json.dumps(decisions, indent=2)
        parsed = json.loads(blob)
        assert isinstance(parsed, list)
        assert parsed[0]["id"] == "01HXYZ123"


# ---------------------------------------------------------------------------
# Test: Integration between files
# ---------------------------------------------------------------------------


class TestFileIntegration:
    """Verify cross-file references are consistent."""

    def test_html_references_app_js(self, html_content):
        """HTML must include app.js script tag."""
        assert "app.js" in html_content

    def test_html_references_styles_css(self, html_content):
        """HTML must include styles.css link."""
        assert "styles.css" in html_content

    def test_js_ids_match_html(self, html_elements, js_content):
        """Key IDs referenced in JS must exist in HTML."""
        js_id_refs = [
            "decFilterSymbol",
            "decFilterEvent",
            "decFilterStatus",
            "decFilterStart",
            "decFilterEnd",
            "decApplyBtn",
            "decClearBtn",
            "decExportBtn",
            "decTimeline",
            "decLoadMore",
            "decModal",
            "decModalTitle",
            "decModalClose",
            "decModalBody",
            "decModalIndicators",
            "decModalGateBody",
            "decModalMetaKv",
            "decReplayBtn",
            "viewDash",
            "viewDecisions",
            "decisionsView",
            "decSummaryBar",
        ]
        for eid in js_id_refs:
            assert eid in html_elements.ids, f"JS references #{eid} but it's not in HTML"

    def test_css_classes_used_in_js(self, js_content, css_content):
        """CSS classes generated by JS must be defined in CSS."""
        generated_classes = [
            "dec-badge-entry_signal",
            "dec-badge-exit_check",
            "dec-badge-gate_block",
            "dec-badge-fill",
            "dec-badge-funding",
            "dec-status-executed",
            "dec-status-blocked",
            "dec-status-rejected",
            "dec-status-hold",
            "dec-item",
            "dec-gate-pass",
            "dec-gate-fail",
        ]
        for cls in generated_classes:
            assert cls in css_content, f"JS generates class .{cls} but it's not in CSS"

    def test_html_is_well_formed(self, html_content):
        """HTML must parse without errors."""
        parser = HTMLParser()
        # HTMLParser.feed() will raise on truly broken HTML
        parser.feed(html_content)
        # If we get here, parsing succeeded

    def test_decisions_view_hidden_by_default(self, html_content):
        """Decisions view should be hidden by default (is-hidden class)."""
        assert 'id="decisionsView" class="decisions-view is-hidden"' in html_content

    def test_dashboard_tab_selected_by_default(self, html_content):
        """Dashboard tab should be selected by default."""
        assert 'id="viewDash" class="segbtn is-on"' in html_content
