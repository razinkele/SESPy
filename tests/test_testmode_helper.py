"""tests/_testmode.py: the pure half of the async test-mode snapshot reader."""
import pytest

from _testmode import export_value


def test_export_value_returns_the_export_entry():
    snap = {"input": {}, "output": {}, "export": {"metrics_cascade": {"a": 1}}}
    assert export_value(snap, "metrics_cascade") == {"a": 1}


def test_export_value_missing_key_is_a_clear_error():
    with pytest.raises(KeyError, match="metrics_cascade"):
        export_value({"input": {}, "output": {}, "export": {}}, "metrics_cascade")
