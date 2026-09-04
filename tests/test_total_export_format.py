from csv import reader
from io import StringIO

import pytest

import models


def _csv_rows(response):
    return list(reader(StringIO(response.data.decode("utf-8-sig"))))


def test_total_csv_export_has_five_columns_and_embeds_element_ratio_in_growth_method(client):
    models.create_sample(
        {
            "id": "total-zh",
            "target_product": "BiNiTe",
            "status": 1,
            "element_ratios": [
                {"element": "Te", "ratio": 1},
                {"element": "Bi", "ratio": 2},
                {"element": "Ni", "ratio": 1},
            ],
            "growth_process": "中文生长流程",
            "growth_process_en": "English growth process",
            "results": "中文结果文字",
            "results_en": "English result text",
        }
    )

    response = client.get("/api/samples/export?lang=zh")

    assert response.status_code == 200
    rows = _csv_rows(response)
    assert rows[0] == ["编号", "目标样品", "是否成功", "结果中的文字", "生长方法"]
    row = next(row for row in rows[1:] if row[0] == "total-zh")
    assert len(row) == 5
    assert row[1] == "BiNiTe"
    assert row[2] == "成功"
    assert row[3] == "中文结果文字"
    assert row[4] == "元素比例：Bi2NiTe\n中文生长流程"


def test_total_csv_english_export_uses_english_fields_and_newline_growth_format(client):
    models.create_sample(
        {
            "id": "total-en",
            "target_product": "BiNiTe",
            "status": 4,
            "element_ratios": [{"element": "Bi", "ratio": 1}],
            "growth_process": "中文生长流程",
            "growth_process_en": "English growth process",
            "results": "中文结果文字",
            "results_en": "English result text",
        }
    )

    response = client.get("/api/samples/export?lang=en")

    assert response.status_code == 200
    rows = _csv_rows(response)
    assert rows[0] == ["Sample ID", "Target Sample", "Status", "Result Text", "Growth Method"]
    row = next(row for row in rows[1:] if row[0] == "total-en")
    assert len(row) == 5
    assert row[1] == "BiNiTe"
    assert row[2] == "Done"
    assert row[3] == "English result text"
    assert row[4] == "Element Ratio: Bi\nEnglish growth process"
    assert "中文生长流程" not in row
    assert "中文结果文字" not in row


@pytest.mark.parametrize(
    ("status", "expected_zh", "expected_en"),
    [
        (0, "失败", "Fail"),
        (1, "成功", "Success"),
        (2, "待定", "Pending"),
        (3, "生长中", "Growing"),
        (4, "生长完成", "Done"),
    ],
)
def test_total_csv_preserves_all_existing_status_labels(client, status, expected_zh, expected_en):
    sample_id = f"total-status-{status}"
    models.create_sample({"id": sample_id, "status": status})

    zh_rows = _csv_rows(client.get("/api/samples/export?lang=zh"))
    en_rows = _csv_rows(client.get("/api/samples/export?lang=en"))

    assert next(row for row in zh_rows[1:] if row[0] == sample_id)[2] == expected_zh
    assert next(row for row in en_rows[1:] if row[0] == sample_id)[2] == expected_en


def test_total_csv_does_not_fallback_when_target_language_fields_are_empty(client):
    models.create_sample(
        {
            "id": "total-empty-en",
            "target_product": "Target",
            "status": 2,
            "element_ratios": [{"element": "Fe", "ratio": 1}],
            "growth_process": "仅中文生长流程",
            "growth_process_en": "",
            "results": "仅中文结果",
            "results_en": "",
        }
    )

    row = next(
        row
        for row in _csv_rows(client.get("/api/samples/export?lang=en"))[1:]
        if row[0] == "total-empty-en"
    )

    assert row[3] == ""
    assert row[4] == "Element Ratio: Fe"
    assert "仅中文生长流程" not in row
    assert "仅中文结果" not in row
