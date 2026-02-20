"""Contract vector tests for the CanonGate pipeline.

Each vector is a committed (fixture, golden) pair. The test asserts byte-
identity between dump_decision(evaluate_shotlist(sl)) and the golden file,
giving us a regression guard that will catch any change in serialization
format, field ordering, or decision logic.
"""
import json
import pathlib

from world_engine.adaptation.models import ShotList
from canon.decision import evaluate_shotlist, dump_decision

_HERE = pathlib.Path(__file__).parent
_FIXTURES = _HERE / "fixtures"
_GOLDENS = _HERE / "goldens"


def _load_shotlist(name: str) -> ShotList:
    with (_FIXTURES / name).open("r", encoding="utf-8") as f:
        return ShotList.model_validate(json.load(f))


def _load_golden(name: str) -> str:
    return (_GOLDENS / name).read_text(encoding="utf-8")


class TestAllowVector:
    def test_byte_identity(self):
        sl = _load_shotlist("allow_shotlist.json")
        got = dump_decision(evaluate_shotlist(sl))
        expected = _load_golden("allow_canon_decision.json")
        assert got == expected

    def test_decision_field(self):
        sl = _load_shotlist("allow_shotlist.json")
        d = evaluate_shotlist(sl)
        assert d.decision == "allow"
        assert d.reasons == []


class TestDenyVector:
    def test_byte_identity(self):
        sl = _load_shotlist("deny_shotlist.json")
        got = dump_decision(evaluate_shotlist(sl))
        expected = _load_golden("deny_canon_decision.json")
        assert got == expected

    def test_deny_reasons_exact(self):
        sl = _load_shotlist("deny_shotlist.json")
        d = evaluate_shotlist(sl)
        assert d.decision == "deny"
        assert d.reasons == ["FORBIDDEN_TOKEN"]
