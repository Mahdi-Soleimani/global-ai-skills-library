"""Path classification helpers shared by collection and registry generation."""


def is_test_fixture_path(path):
    """Return True for explicit fixture paths under evaluation or test trees."""
    parts = [part.casefold() for part in str(path).replace("\\", "/").split("/") if part]
    fixture_index = next((i for i, part in enumerate(parts) if part in {"fixture", "fixtures"}), None)
    if fixture_index is None:
        return False
    return any(part in {"eval", "evals", "test", "tests"} for part in parts[:fixture_index])
