import io
import json

from folio import cli
from folio.serialize import dump, load, load_file, save


def test_round_trip(world, tmp_path):
    s = world["store"]
    s.suspend_user(world["marcus"])
    path = tmp_path / "f.json"
    save(s, path)
    again = load_file(path)
    assert dump(again) == dump(s)
    new_doc = again.create_document(world["harbour"], "Next", world["olive"])
    assert new_doc not in s.documents


def test_sample_loads(sample_path):
    s = load(json.loads(sample_path.read_text()))
    assert len(s.workspaces) == 1
    assert any(g.subgroups for g in s.groups.values())
    assert any(d.restricted for d in s.documents.values())


def _run(*argv):
    out = io.StringIO()
    code = cli.main(list(argv), out=out)
    return code, out.getvalue()


def test_cli_tree_and_groups(sample_path):
    code, text = _run("--data", str(sample_path), "tree")
    assert code == 0 and "Harbour Library/" in text and "Old fee proposal" not in text
    code, text = _run("--data", str(sample_path), "tree", "--all")
    assert "[trashed]" in text and "[restricted]" in text
    code, text = _run("--data", str(sample_path), "groups")
    assert code == 0 and "Architects" in text


def test_cli_show_owner_only(sample_path, capsys):
    code, text = _run("--data", str(sample_path), "show", "doc_0001", "--as", "usr_0002")
    assert code == 0 and "reading room" in text
    code, _ = _run("--data", str(sample_path), "show", "doc_0001", "--as", "usr_0003")
    assert code == 1


def test_cli_search(sample_path):
    code, text = _run("--data", str(sample_path), "search", "tide", "--as", "usr_0002")
    assert code == 0 and "doc_0002" in text
