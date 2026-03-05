"""
Tests for tool_common.report
============================
Foundation invariant tests: every tool in the ecosystem relies on
canonical_json(), so we verify its contract explicitly.

Tests
-----
1. Same dict produces byte-identical string across two independent calls
2. Output ends with exactly one trailing newline
3. Keys are sorted (sort_keys=True contract)
4. Compact separators — no spaces after ":" or ","
5. Non-ASCII characters survive (ensure_ascii=False)
6. Nested structures are serialized deterministically
7. Empty dict produces "{}\n"
"""
from __future__ import annotations

from tool_common.report import canonical_json


class TestCanonicalJson:
    def test_same_dict_byte_identical_across_two_calls(self) -> None:  # 1
        obj = {"z": 1, "a": 2, "m": [3, 1, 2]}
        assert canonical_json(obj) == canonical_json(obj)

    def test_ends_with_exactly_one_newline(self) -> None:  # 2
        result = canonical_json({"key": "value"})
        assert result.endswith("\n")
        assert not result.endswith("\n\n")

    def test_keys_are_sorted(self) -> None:  # 3
        obj = {"z": 1, "a": 2, "m": 3}
        result = canonical_json(obj)
        assert result == '{"a":2,"m":3,"z":1}\n'

    def test_compact_separators_no_spaces(self) -> None:  # 4
        result = canonical_json({"a": 1, "b": 2})
        # Canonical form must not have spaces around ":" or after ","
        assert " " not in result.rstrip("\n")

    def test_non_ascii_survives(self) -> None:  # 5
        obj = {"name": "résumé", "emoji": "✓", "cjk": "工具"}
        result = canonical_json(obj)
        assert "résumé" in result
        assert "✓" in result
        assert "工具" in result
        # Confirm no \uXXXX escapes were produced
        assert "\\u" not in result

    def test_nested_structure_deterministic(self) -> None:  # 6
        obj = {
            "summary": {"error": 1, "ok": 3, "warn": 2},
            "results": [{"b": 2, "a": 1}],
        }
        # Nested dict keys must also be sorted
        expected = '{"results":[{"a":1,"b":2}],"summary":{"error":1,"ok":3,"warn":2}}\n'
        assert canonical_json(obj) == expected

    def test_empty_dict(self) -> None:  # 7
        assert canonical_json({}) == "{}\n"
