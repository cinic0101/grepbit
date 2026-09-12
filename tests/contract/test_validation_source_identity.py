"""Evidence identity must include runtime data as well as Python source."""

from pathlib import Path

from tools import verify

PACK = Path("src/grepbit/resources/unsupported_shapes.json")


def test_packaged_language_rules_are_part_of_source_identity():
    assert verify._is_relevant_source_path(PACK)


def test_resource_only_change_invalidates_source_digest(tmp_path, monkeypatch):
    pack = tmp_path / PACK
    pack.parent.mkdir(parents=True)
    pack.write_text('{"revision": "before"}')
    monkeypatch.setattr(verify, "ROOT", tmp_path)

    def git_output(*args):
        if args == ("ls-files", "-z"):
            return PACK.as_posix() + "\0"
        if args == ("rev-parse", "HEAD"):
            return "fixed-test-head"
        return ""

    monkeypatch.setattr(verify, "_git_output", git_output)
    before = verify._source_snapshot()
    pack.write_text('{"revision": "after"}')
    after = verify._source_snapshot()
    assert before["available"] and after["available"]
    assert before["tracked_source_digest"] != after["tracked_source_digest"]
    assert PACK.as_posix() in after["tracked_source_hashes"]


def test_resource_inclusion_does_not_bypass_environment_guard():
    assert verify._is_environment_path(PACK.parent / ".env")
