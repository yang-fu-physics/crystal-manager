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
    assert match, f"{name}() must be implemented before this contract can pass"
    return match.group("body")


def test_growth_form_has_two_persistent_textareas_and_header_translation_button():
    assert 'id="growthProcessZhField"' in HTML
    assert 'id="growthProcessEnField"' in HTML
    assert 'id="growthProcess"' not in HTML
    assert 'id="translateGrowthBtn"' in HTML
    assert 'data-i18n="form.translateGrowthBtn">en to cn</span>' in HTML
    assert 'data-i18n="form.translateGrowthBtn">cn to en</span>' not in HTML
    growth_start = HTML.index('<!-- 生长流程 -->')
    growth_end = HTML.index('<!-- 结果 -->')
    growth_section = HTML[growth_start:growth_end]
    assert 'class="growth-header-actions"' in growth_section
    assert growth_section.index('translateGrowthBtn') < growth_section.index('section-sample-id-display')


def test_growth_i18n_and_language_switch_map_directions():
    assert 'translateGrowthBtn: "en to cn"' in JS
    assert 'translateGrowthBtn: "cn to en"' in JS
    assert 'translateGrowthTitle' in JS
    body = _function_body("updateGrowthLanguageUI")
    assert 'growthProcessZhFieldInput.hidden = !showChinese;' in body
    assert 'growthProcessEnFieldInput.hidden = showChinese;' in body
    assert 'currentLang === \'zh\'' in body


def test_growth_translation_uses_endpoint_and_only_updates_draft_target():
    body = _function_body("translateGrowthProcess")
    assert "const sourceField = showChinese ? growthProcessEnFieldInput : growthProcessZhFieldInput;" in body
    assert "const targetField = showChinese ? growthProcessZhFieldInput : growthProcessEnFieldInput;" in body
    assert "fetch('/api/results/translate'" in body
    assert "targetField.value = translation;" in body
    assert "growthProcessZhFieldInput.value = translation;" not in body
    assert "growthProcessEnFieldInput.value = translation;" not in body
    assert "saveSample(" not in body
    assert "loadSampleList(" not in body
    assert "selectSample(" not in body
    assert "fillForm(" not in body
    assert "translateGrowthBtn.disabled = true;" in body
    assert "translateGrowthBtn.setAttribute('aria-busy', 'true');" in body
    assert "translateGrowthBtn.disabled = false;" in body
    assert "translateGrowthBtn.removeAttribute('aria-busy');" in body


def test_growth_translation_button_is_bound_once():
    assert JS.count("translateGrowthBtn.addEventListener('click'") == 1


def test_growth_fields_participate_in_new_fill_save_and_copy_lifecycles():
    assert "const growthProcessZhFieldInput = document.getElementById('growthProcessZhField');" in JS
    assert "const growthProcessEnFieldInput = document.getElementById('growthProcessEnField');" in JS
    create_body = _function_body("createNewSample")
    fill_body = _function_body("fillForm")
    copy_body = _function_body("copySample")
    assert "growthProcessZhFieldInput.value = '';" in create_body
    assert "growthProcessEnFieldInput.value = '';" in create_body
    assert "growthProcessZhFieldInput.value = sample.growth_process || '';" in fill_body
    assert "growthProcessEnFieldInput.value = sample.growth_process_en || '';" in fill_body
    assert "growthProcessZhFieldInput.value = originalData.growth_process || '';" in copy_body
    assert "growthProcessEnFieldInput.value = originalData.growth_process_en || '';" in copy_body
    assert "growth_process: growthProcessZhFieldInput.value.trim()," in JS
    assert "growth_process_en: growthProcessEnFieldInput.value.trim()," in JS


def test_growth_toolbar_css_reuses_responsive_results_layout():
    assert ".growth-header-actions" in CSS
    assert ".growth-toolbar" in CSS
    assert ".growth-header-actions" in CSS[CSS.index("@media (max-width: 900px)"):]
    assert ".growth-toolbar" in CSS[CSS.index("@media (max-width: 900px)"):]
