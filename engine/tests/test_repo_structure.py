from pathlib import Path


def test_no_nested_engine_folder():
    engine_root = Path(__file__).resolve().parent.parent
    nested = engine_root / "engine"
    assert not nested.exists(), (
        "found engine/engine/ -- there is only one engine folder (the one with "
        "pyproject.toml); source modules go directly inside it"
    )
