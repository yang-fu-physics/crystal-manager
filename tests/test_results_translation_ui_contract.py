from pathlib import Path
import re


APP_JS = Path(__file__).parents[1] / "static" / "js" / "app.js"


def _translate_results_body():
    source = APP_JS.read_text(encoding="utf-8")
    match = re.search(
        r"async function translateResults\(\) \{(?P<body>.*?)\n\}\n\nfunction closeSidebar",
        source,
        flags=re.DOTALL,
    )
    assert match, "translateResults() must be implemented before this contract can pass"
    return source, match.group("body")


def test_translate_results_ui_contract_is_bidirectional_and_unsaved():
    source, body = _translate_results_body()

    assert 'translateResultsBtn: "en to cn"' in source
    assert 'translateResultsBtn: "cn to en"' in source
    assert "fetch('/api/results/translate'" in body
    assert "method: 'POST'" in body
    assert "text: sourceText" in body
    assert "source_lang: sourceLang" in body
    assert "target_lang: targetLang" in body
    assert "const sourceLang = showChinese ? 'en' : 'zh';" in body
    assert "const targetLang = showChinese ? 'zh' : 'en';" in body
    assert "const sourceField = showChinese ? resultsEnFieldInput : resultsZhFieldInput;" in body
    assert "const targetField = showChinese ? resultsZhFieldInput : resultsEnFieldInput;" in body
    assert "const sourceText = sourceField.value.trim();" in body
    assert "targetField.value = translation;" in body
    assert "autoResizeTextarea(targetField);" in body
    assert "messages.translateSourceEmpty" in body
    assert "messages.translationCompleteUnsaved" in body
    assert "messages.translationFailed" in body
    assert "translateResultsBtn.disabled = true;" in body
    assert "translateResultsBtn.setAttribute('aria-busy', 'true');" in body
    assert "translateResultsBtn.disabled = false;" in body
    assert "translateResultsBtn.removeAttribute('aria-busy');" in body
    assert "translation.trim()" in body
    assert "finally" in body

    # Translation must never persist, reload, or replace the captured draft.
    assert "saveSample(" not in body
    assert "loadSampleList(" not in body
    assert "selectSample(" not in body
    assert "fillForm(" not in body
    assert "/api/samples" not in body

    assert source.count("translateResultsBtn.addEventListener('click'") == 1
