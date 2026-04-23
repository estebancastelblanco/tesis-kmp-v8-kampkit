"""Tests for Kotlin parser (tree-sitter + regex fallback)."""

from pathlib import Path

from kmp_impact_analyzer.phase2_static.kotlin_parser import parse_kotlin_file, _parse_with_regex

FIXTURES = Path(__file__).parent / "fixtures" / "sample_kotlin"


def test_parse_package_and_imports():
    result = parse_kotlin_file(FIXTURES / "CommonModule.kt")
    assert result.package == "com.example.common"
    assert any("io.ktor" in i for i in result.imports)


def test_parse_class_declaration():
    result = parse_kotlin_file(FIXTURES / "CommonModule.kt")
    names = [d.name for d in result.declarations]
    assert "ExpenseRepoImpl" in names


def test_parse_expect_modifier():
    result = parse_kotlin_file(FIXTURES / "ExpectClass.kt")
    expect_decls = [d for d in result.declarations if d.is_expect]
    assert len(expect_decls) >= 1
    assert expect_decls[0].name == "DatabaseDriverFactory"


def test_parse_actual_modifier():
    result = parse_kotlin_file(FIXTURES / "ActualAndroid.kt")
    actual_decls = [d for d in result.declarations if d.is_actual]
    assert len(actual_decls) >= 1
    assert actual_decls[0].name == "DatabaseDriverFactory"


def test_regex_fallback_parses_package():
    source = (FIXTURES / "CommonModule.kt").read_text()
    result = _parse_with_regex(source, "CommonModule.kt")
    assert result.package == "com.example.common"


def test_regex_fallback_parses_expect():
    source = (FIXTURES / "ExpectClass.kt").read_text()
    result = _parse_with_regex(source, "ExpectClass.kt")
    expect_decls = [d for d in result.declarations if d.is_expect]
    assert len(expect_decls) >= 1
