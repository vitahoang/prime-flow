# jotter

My notes: a folder of Markdown files with a bit of front matter on top.
jotter is a small library and CLI around that folder. It does not own the
files; I edit them in whatever editor is open, and sync them with Syncthing.

    python -m jotter new "Garden plan" --tag garden --edit
    python -m jotter list --tag work --since 30
    python -m jotter list --archived --long
    python -m jotter show garden-plan
    python -m jotter tags
    python -m jotter tag add garden-plan balcony
    python -m jotter archive old-apartment-move-checklist
    python -m jotter links garden-plan --back
    python -m jotter check

The vault is `--vault DIR`, else `$JOTTER_VAULT`, else `~/Notes`. Set
`JOTTER_NOW=YYYY-MM-DDTHH:MM:SS` to run as if it were another time.
`vault/` in this repo is a small sample vault used by the tests.

## Notes

Every `*.md` file directly in the vault folder is a note (names starting with
`.` or `_` are skipped):

    ---
    title: Sourdough starter
    tags: [baking, food]
    created: 2022-03-20T18:00:00
    updated: 2023-01-08T10:00:00
    ---
    Feed 1:1:1 every 12 hours...

| Key | What |
|---|---|
| `title` | shown everywhere; the file name is the slug of the first title |
| `tags` | list of tags; inline `#tags` in the body count too |
| `created`, `updated` | local ISO times; `jotter` bumps `updated` when it saves |
| `archived` | `true` hides the note from `list` and `tags` |
| `aliases` | other names `show` and `links` accept |
| `source` | `evernote` for notes brought over by the 2021 import |

`jotter list` shows newest first by creation date.

## Tags

Front-matter tags plus inline `#tags`. Nested tags
use `/` (`clients/dupont`) and `tags --nested` also counts the parents.

## Links

`[[Title]]`, `[[Title|label]]` and `[[Title#Heading]]`. `jotter check` reports
links that point nowhere, along with bad dates and duplicate titles.

## Search

Not built yet. `grep -ril WORD ~/Notes` does the job for now.

## Library

    from jotter.store import Store
    store = Store("~/Notes")
    for note in store.notes(include_archived=False):
        print(note.path, note.title, note.tags, note.updated)

`Store` keeps parsed notes in memory, so it is cheap to call `notes()` often.
