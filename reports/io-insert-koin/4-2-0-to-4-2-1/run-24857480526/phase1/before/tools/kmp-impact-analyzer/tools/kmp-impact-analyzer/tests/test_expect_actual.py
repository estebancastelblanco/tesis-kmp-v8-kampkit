"""Tests for expect/actual resolver."""

from kmp_impact_analyzer.contracts import FileParseResult, KotlinDeclaration, DeclarationKind
from kmp_impact_analyzer.phase2_static.expect_actual import ExpectActualResolver


def _make_parse_result(file_path, package, declarations):
    return FileParseResult(
        file_path=file_path,
        package=package,
        declarations=declarations,
    )


def test_pairs_expect_with_actual():
    results = [
        _make_parse_result("common/Expect.kt", "com.example", [
            KotlinDeclaration(
                kind=DeclarationKind.CLASS,
                name="DbFactory",
                fqcn="com.example.DbFactory",
                is_expect=True,
                file_path="common/Expect.kt",
            )
        ]),
        _make_parse_result("android/Actual.kt", "com.example", [
            KotlinDeclaration(
                kind=DeclarationKind.CLASS,
                name="DbFactory",
                fqcn="com.example.DbFactory",
                is_actual=True,
                file_path="android/Actual.kt",
            )
        ]),
    ]

    resolver = ExpectActualResolver()
    resolver.build(results)

    assert len(resolver.pairs) == 1
    assert resolver.pairs[0].expect_file == "common/Expect.kt"
    assert "android/Actual.kt" in resolver.pairs[0].actual_files


def test_linked_files():
    results = [
        _make_parse_result("common/Expect.kt", "com.example", [
            KotlinDeclaration(
                kind=DeclarationKind.CLASS, name="X", fqcn="com.example.X",
                is_expect=True, file_path="common/Expect.kt",
            )
        ]),
        _make_parse_result("ios/Actual.kt", "com.example", [
            KotlinDeclaration(
                kind=DeclarationKind.CLASS, name="X", fqcn="com.example.X",
                is_actual=True, file_path="ios/Actual.kt",
            )
        ]),
    ]
    resolver = ExpectActualResolver()
    resolver.build(results)

    linked = resolver.get_linked_files("common/Expect.kt")
    assert "ios/Actual.kt" in linked

    linked2 = resolver.get_linked_files("ios/Actual.kt")
    assert "common/Expect.kt" in linked2
