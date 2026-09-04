from pathlib import Path
import re


ROOT = Path(__file__).parents[1]
HTML = (ROOT / "templates/index.html").read_text(encoding="utf-8")
JS = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/css/style.css").read_text(encoding="utf-8")


def _function_body(name):
    match = re.search(
        rf"(?:async )?function {name}\([^)]*\) \{{(?P<body>.*?)\n\}}",
        JS,
        re.S,
    )
    assert match, f"{name}() must be implemented"
    return match.group("body")


def test_export_selection_dialog_has_accessible_controls_and_bilingual_labels():
    assert 'id="exportSelectionModal"' in HTML
    assert 'role="dialog"' in HTML
    assert 'aria-modal="true"' in HTML
    assert 'data-i18n-attr="aria-label|exportSelection.close"' in HTML
    assert 'id="exportSelectionList"' in HTML
    assert 'id="exportSelectionSelectAllBtn"' in HTML
    assert 'id="exportSelectionClearAllBtn"' in HTML
    assert 'id="exportSelectionCount"' in HTML
    assert 'id="exportSelectionCancelBtn"' in HTML
    assert 'id="exportSelectionConfirmBtn"' in HTML
    assert 'exportSelection:' in JS
    assert 'exportSelection.selectAll' in HTML
    assert 'exportSelection.clearAll' in HTML
    assert 'exportSelection.confirm' in HTML


def test_both_export_buttons_open_the_shared_selection_flow():
    csv_body = _function_body("exportSamples")
    pptx_body = _function_body("exportSamplesPptx")
    assert "openExportSelection('csv')" in csv_body
    assert "openExportSelection('pptx')" in pptx_body
    assert "function openExportSelection(format)" in JS
    assert "let pendingExportFormat" in JS


def test_selection_confirm_posts_sample_ids_to_the_matching_export_endpoint():
    body = _function_body("downloadSelectedExport")
    assert "method: 'POST'" in body
    assert "'Content-Type': 'application/json'" in body
    assert "JSON.stringify({ sample_ids: sampleIds })" in body
    assert "/api/samples/export?lang=${currentLang}" in body
    assert "/api/samples/export_pptx?lang=${currentLang}" in body
    confirm_body = _function_body("confirmExportSelection")
    assert "downloadSelectedExport(pendingExportFormat, sampleIds)" in confirm_body
    assert "exportSelectionConfirmBtn.disabled = true;" in confirm_body
    assert "exportSelectionConfirmBtn.disabled = false;" in confirm_body


def test_selection_rendering_uses_dom_text_content_and_defaults_to_all_checked():
    body = _function_body("renderExportSelectionSamples")
    assert "document.createElement" in body
    assert ".textContent" in body
    assert ".checked = true" in body
    assert ".innerHTML" not in body
    assert "target_product" in body


def test_empty_selection_does_not_send_export_request_and_dialog_can_close():
    body = _function_body("confirmExportSelection")
    assert "if (sampleIds.length === 0)" in body
    assert "exportSelectionEmpty" in body
    assert "return;" in body
    assert "closeExportSelection()" in JS
    assert "key === 'Escape'" in JS or 'event.key === \'Escape\'' in JS


def test_selection_requests_cannot_close_or_overwrite_a_new_dialog():
    assert "let exportSelectionBusy = false;" in JS
    assert "let exportSelectionRequestId = 0;" in JS
    assert "if (exportSelectionBusy && !force) return;" in JS
    assert "exportSelectionBusy) return;" in JS
    assert "const requestId = ++exportSelectionRequestId;" in JS
    assert "if (requestId !== exportSelectionRequestId) return;" in JS
    assert "exportSelectionBusy = true;" in JS
    assert "exportSelectionBusy = false;" in JS


def test_selection_css_is_responsive_and_does_not_reuse_image_modal():
    assert ".export-selection-overlay" in CSS
    assert ".export-selection-list" in CSS
    assert ".export-selection-dialog" in CSS
    assert ".export-selection-overlay[hidden]" in CSS
    media_start = CSS.find("@media (max-width: 900px)")
    assert media_start >= 0
    assert ".export-selection-dialog" in CSS[media_start:]
