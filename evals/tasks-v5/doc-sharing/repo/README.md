# folio

A small document store for the Hollis & Grey studio: workspaces, nested
folders, documents with revisions and comments, people and groups. Python 3.10+,
no dependencies.

## Model

- **Workspace**: one per company. Has an email `domain`; anyone on another
  domain is a guest. Workspace `admins` manage people and groups.
- **User**: belongs to one workspace. `status` is `active` or `suspended`.
- **Group**: a flat list of people in a workspace, used for @-mentions and
  (soon) sharing.
- **Folder**: nested with `parent_id`; has an owner.
- **Document**: lives in a folder; has an owner, a body, revisions and
  comments. `restricted` is a legacy flag from the v1 importer. Trashed
  documents stay in the store with `trashed = True` until someone restores them.

Ids carry their kind: `ws_0001`, `usr_0003`, `grp_0002`, `fld_0004`, `doc_0010`.

## Access

Only a document's owner can read, edit or comment on it (`folio/access.py`).
Sharing is the next thing on the list.

## Using it

```python
from folio.store import Store

s = Store()
ws = s.add_workspace("Hollis & Grey", domain="hollisgrey.com")
olive = s.add_user(ws, "olive@hollisgrey.com", "Olive")
projects = s.create_folder(ws, "Projects", olive)
doc = s.create_document(projects, "Site visit notes", olive)
```

Other setup helpers on `Store`: `add_admin`, `suspend_user`, `reactivate_user`,
`add_group`, `add_member`, `add_subgroup`, `move_document`, `set_restricted`,
`trash_document`, `restore_document`.

## CLI

```
python -m folio --data data/sample_workspace.json tree --all
python -m folio --data data/sample_workspace.json groups
python -m folio --data data/sample_workspace.json show doc_0001 --as usr_0002
```

`data/sample_workspace.json` is rebuilt by `tools/make_sample.py`.

## Tests

```
python -m pytest
```
