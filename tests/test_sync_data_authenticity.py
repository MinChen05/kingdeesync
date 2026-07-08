from src.core.sync_data_authenticity import compare_date, compare_decimal, compare_string


def test_compare_decimal_accepts_equivalent_scale():
    assert compare_decimal("12.500000", "12.5").matched is True


def test_compare_decimal_reports_difference():
    result = compare_decimal("0", "1872000.0000000000")
    assert result.matched is False
    assert result.db_value == "0"
    assert result.api_value == "1872000.0000000000"


def test_compare_string_trims_spaces():
    assert compare_string(" MAT-001 ", "MAT-001").matched is True


def test_compare_date_compares_to_seconds():
    result = compare_date("2026-07-08 10:20:07.833333", "2026-07-08T10:20:07.833")
    assert result.matched is True
