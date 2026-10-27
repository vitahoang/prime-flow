from jotter import importer

ENEX = """<?xml version="1.0" encoding="UTF-8"?>
<en-export>
  <note>
    <title>Halden glossary</title>
    <content><![CDATA[<en-note><div>notwithstanding -&gt; nonobstant</div><ul><li>one</li><li>two</li></ul></en-note>]]></content>
    <created>20200114T130000Z</created>
    <tag>terminology</tag>
  </note>
</en-export>
"""


def test_import_enex(store, tmp_path):
    path = tmp_path / "export.enex"
    path.write_text(ENEX, encoding="utf-8")
    notes = importer.import_enex(store, path, notebook="Work")
    assert len(notes) == 1
    note = store.get("halden-glossary")
    assert note.tags == ["Work", "terminology"]
    assert note.meta["source"] == "evernote"
    assert "notwithstanding -> nonobstant" in note.body
    assert "- one" in note.body
    assert note.meta["created"] == "2020-01-14T13:00:00"
