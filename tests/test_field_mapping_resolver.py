from __future__ import annotations

import unittest


class FieldMappingResolverTests(unittest.TestCase):
    def test_resolve_prefers_first_present_source_alias_when_both_are_present(self) -> None:
        from src.core.field_mapping_resolver import FieldMappingResolver

        resolver = FieldMappingResolver(
            {
                "prd_mo": {
                    "FCANCELSTATUS": {
                        "sources": [
                            "FCANCELSTATUS",
                            "FCancelStatus",
                            "FcancelStatus",
                            "F_Cancel_Status",
                        ],
                        "type": "string",
                        "default": "",
                    }
                }
            }
        )

        result = resolver.resolve_field(
            "prd_mo",
            "FCANCELSTATUS",
            {"FCANCELSTATUS": "A", "FCancelStatus": "B", "FcancelStatus": "C"},
        )

        self.assertEqual(result, "A")

    def test_resolve_falls_back_to_second_alias_when_first_is_none(self) -> None:
        from src.core.field_mapping_resolver import FieldMappingResolver

        resolver = FieldMappingResolver(
            {
                "ap_payable": {
                    "FNOTAXAMOUNTFOR": {
                        "sources": [
                            "FNoTaxAmountFor_D",
                            "FNOTAXAMOUNTFOR_D",
                            "FNoTaxAmountFor",
                            "FNOTAXAMOUNTFOR",
                        ],
                        "type": "decimal",
                        "default": 0.0,
                    }
                }
            }
        )

        result = resolver.resolve_field(
            "ap_payable",
            "FNOTAXAMOUNTFOR",
            {"FNoTaxAmountFor_D": None, "FNOTAXAMOUNTFOR_D": "222.25"},
        )

        self.assertEqual(result, 222.25)

    def test_resolve_falls_back_to_second_alias_when_first_is_blank(self) -> None:
        from src.core.field_mapping_resolver import FieldMappingResolver

        resolver = FieldMappingResolver(
            {
                "prd_mo": {
                    "FCANCELSTATUS": {
                        "sources": [
                            "FCANCELSTATUS",
                            "FCancelStatus",
                            "FcancelStatus",
                            "F_Cancel_Status",
                        ],
                        "type": "string",
                        "default": "",
                    }
                }
            }
        )

        result = resolver.resolve_field(
            "prd_mo",
            "FCANCELSTATUS",
            {"FCANCELSTATUS": "", "FCancelStatus": "B"},
        )

        self.assertEqual(result, "B")

    def test_resolve_prefers_first_present_source_alias(self) -> None:
        from src.core.field_mapping_resolver import FieldMappingResolver

        resolver = FieldMappingResolver(
            {
                "ap_payable": {
                    "FNOTAXAMOUNTFOR": {
                        "sources": [
                            "FNoTaxAmountFor_D",
                            "FNOTAXAMOUNTFOR_D",
                            "FNoTaxAmountFor",
                            "FNOTAXAMOUNTFOR",
                        ],
                        "type": "decimal",
                        "default": 0.0,
                    }
                }
            }
        )

        result = resolver.resolve_field(
            "ap_payable",
            "FNOTAXAMOUNTFOR",
            {"FNOTAXAMOUNTFOR_D": "100.50"},
        )

        self.assertEqual(result, 100.5)

    def test_resolve_uses_default_when_all_sources_are_missing(self) -> None:
        from src.core.field_mapping_resolver import FieldMappingResolver

        resolver = FieldMappingResolver(
            {
                "prd_mo": {
                    "FCANCELSTATUS": {
                        "sources": [
                            "FCANCELSTATUS",
                            "FCancelStatus",
                            "FcancelStatus",
                            "F_Cancel_Status",
                        ],
                        "type": "string",
                        "default": "",
                    }
                }
            }
        )

        result = resolver.resolve_field("prd_mo", "FCANCELSTATUS", {})

        self.assertEqual(result, "")

    def test_resolve_uses_default_when_decimal_input_is_invalid(self) -> None:
        from src.core.field_mapping_resolver import FieldMappingResolver

        resolver = FieldMappingResolver(
            {
                "ap_payable": {
                    "FNOTAXAMOUNTFOR": {
                        "sources": [
                            "FNoTaxAmountFor_D",
                            "FNOTAXAMOUNTFOR_D",
                            "FNoTaxAmountFor",
                            "FNOTAXAMOUNTFOR",
                        ],
                        "type": "decimal",
                        "default": 0.0,
                    }
                }
            }
        )

        result = resolver.resolve_field(
            "ap_payable",
            "FNOTAXAMOUNTFOR",
            {"FNOTAXAMOUNTFOR_D": "not-a-number"},
        )

        self.assertEqual(result, 0.0)

    def test_resolve_trims_string_by_max_length_when_policy_is_trim(self) -> None:
        from src.core.field_mapping_resolver import FieldMappingResolver

        resolver = FieldMappingResolver(
            {
                "eng_bomchild": {
                    "FCHILDNAME": {
                        "sources": [
                            "FMATERIALIDCHILD.FNAME",
                            "FMATERIALIDCHILD.FName",
                            "FCHILDNAME",
                            "FChildName",
                        ],
                        "type": "string",
                        "default": "",
                        "max_length": 5,
                        "truncate_policy": "trim",
                    }
                }
            }
        )

        result = resolver.resolve_field(
            "eng_bomchild",
            "FCHILDNAME",
            {"FMATERIALIDCHILD.FNAME": "ABCDEFG"},
        )

        self.assertEqual(result, "ABCDE")

    def test_resolve_rejects_overlong_string_when_policy_is_reject(self) -> None:
        from src.core.field_mapping_resolver import FieldMappingResolver

        resolver = FieldMappingResolver(
            {
                "eng_bomchild": {
                    "FCHILDNAME": {
                        "sources": [
                            "FMATERIALIDCHILD.FNAME",
                            "FMATERIALIDCHILD.FName",
                            "FCHILDNAME",
                            "FChildName",
                        ],
                        "type": "string",
                        "default": "",
                        "max_length": 5,
                        "truncate_policy": "reject",
                    }
                }
            }
        )

        with self.assertRaises(ValueError):
            resolver.resolve_field(
                "eng_bomchild",
                "FCHILDNAME",
                {"FMATERIALIDCHILD.FNAME": "ABCDEFG"},
            )

    def test_resolve_returns_original_value_when_field_has_no_rule(self) -> None:
        from src.core.field_mapping_resolver import FieldMappingResolver

        resolver = FieldMappingResolver({})

        result = resolver.resolve_field("prd_mo", "FCANCELSTATUS", {"FCANCELSTATUS": "A"})

        self.assertEqual(result, "A")


if __name__ == "__main__":
    unittest.main()
