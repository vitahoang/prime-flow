"""Command line: `python -m jotter <command>`."""

import argparse
import subprocess
import sys
from collections import Counter
from datetime import timedelta

from jotter import archive, check, clock, config, formatting, importer, links, search
from jotter import tags as tagmod
from jotter.store import NoteNotFound, Store


def _store(args):
    return Store(config.vault_path(args.vault))


def _note(store, name):
    try:
        return store.get(name)
    except NoteNotFound:
        raise SystemExit(f"jotter: no note called {name!r}")


# --- commands ---------------------------------------------------------------

def cmd_new(args):
    store = _store(args)
    body = sys.stdin.read() if args.stdin else ""
    note = store.create(args.title, tags=args.tag or (), body=body)
    print(note.path)
    if args.edit:
        subprocess.call([config.editor(), str(note.path)])
    return 0


def cmd_list(args):
    store = _store(args)
    notes = store.notes(include_archived=args.archived)
    if args.tag:
        notes = [n for n in notes if n.has_tag(args.tag)]
    if args.since:
        cutoff = clock.now() - timedelta(days=args.since)
        notes = [n for n in notes if n.updated and n.updated >= cutoff]
    # Newest first by creation date.
    notes.sort(key=lambda n: (n.updated is None, n.updated), reverse=False)
    notes.reverse()
    if args.limit:
        notes = notes[: args.limit]
    if args.json:
        print(formatting.as_json([formatting.note_row(n, args.long) for n in notes]))
    elif notes:
        print(formatting.notes_table(notes, long=args.long))
    return 0


def cmd_show(args):
    store = _store(args)
    note = _note(store, args.name)
    if args.json:
        row = formatting.note_row(note, long=True)
        row["links"] = note.links
        row["body"] = note.body
        print(formatting.as_json(row))
    else:
        print(note.to_text(), end="")
    return 0


def cmd_tags(args):
    store = _store(args)
    notes = store.notes(include_archived=args.archived)
    if args.nested:
        counts = tagmod.TagIndex(notes).counts()
    else:
        counts = dict(Counter(t for n in notes for t in n.tags))
    if args.json:
        print(formatting.as_json(counts))
    elif counts:
        print(formatting.tag_counts(counts))
    return 0


def cmd_tag(args):
    store = _store(args)
    note = _note(store, args.name)
    change = tagmod.add_tag if args.action == "add" else tagmod.remove_tag
    changed = [t for t in args.tags if change(note, t)]
    if changed:
        store.save(note)
    print(f"{note.path.name}: {', '.join(note.tags) or '(no tags)'}")
    return 0


def cmd_rename_tag(args):
    store = _store(args)
    changed = tagmod.rename_tag(store, args.old, args.new)
    print(f"renamed {args.old} -> {args.new} in {len(changed)} note(s)")
    return 0


def cmd_archive(args):
    store = _store(args)
    fn = archive.unarchive if args.undo else archive.archive
    for name in args.names:
        note = _note(store, name)
        done = fn(store, note)
        state = "unarchived" if args.undo else "archived"
        print(f"{note.path.name}: {state if done else 'unchanged'}")
    return 0


def cmd_links(args):
    store = _store(args)
    note = _note(store, args.name)
    if args.back:
        for other in links.backlinks(store, note):
            print(other.path.name)
        return 0
    for target, path in links.outgoing(store, note):
        print(f"{target} -> {path.name if path else '(missing)'}")
    return 0


def cmd_check(args):
    store = _store(args)
    found = check.problems(store)
    for name, message in found:
        print(f"{name}: {message}")
    if not found:
        print("ok")
    return 1 if found else 0


def cmd_search(args):
    store = _store(args)
    for result in search.search(store, " ".join(args.query), limit=args.limit):
        print(result.path)
    return 0


def cmd_import(args):
    store = _store(args)
    notes = importer.import_enex(store, args.file, notebook=args.notebook, dry_run=args.dry_run)
    verb = "would import" if args.dry_run else "imported"
    print(f"{verb} {len(notes)} note(s)")
    return 0


# --- parser -----------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="jotter", description="Markdown notes in a folder.")
    p.add_argument("--vault", help="vault folder (default: $JOTTER_VAULT or ~/Notes)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("new", help="create a note")
    s.add_argument("title")
    s.add_argument("--tag", action="append", help="tag (repeatable)")
    s.add_argument("--stdin", action="store_true", help="read the body from stdin")
    s.add_argument("--edit", action="store_true", help="open it in $EDITOR")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("list", help="list notes, newest first")
    s.add_argument("--tag")
    s.add_argument("--since", type=int, metavar="DAYS")
    s.add_argument("--limit", type=int)
    s.add_argument("--archived", action="store_true", help="include archived notes")
    s.add_argument("--long", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="print a note")
    s.add_argument("name")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("tags", help="every tag with its note count")
    s.add_argument("--archived", action="store_true")
    s.add_argument("--nested", action="store_true", help="also count parents of nested tags")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_tags)

    s = sub.add_parser("tag", help="add or remove tags on a note")
    s.add_argument("action", choices=["add", "rm"])
    s.add_argument("name")
    s.add_argument("tags", nargs="+")
    s.set_defaults(func=cmd_tag)

    s = sub.add_parser("rename-tag", help="rename a tag everywhere")
    s.add_argument("old")
    s.add_argument("new")
    s.set_defaults(func=cmd_rename_tag)

    s = sub.add_parser("archive", help="archive notes")
    s.add_argument("names", nargs="+")
    s.add_argument("--undo", action="store_true")
    s.set_defaults(func=cmd_archive)

    s = sub.add_parser("links", help="outgoing links (or --back for backlinks)")
    s.add_argument("name")
    s.add_argument("--back", action="store_true")
    s.set_defaults(func=cmd_links)

    s = sub.add_parser("check", help="find notes with problems")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("search", help="search notes by keyword")
    s.add_argument("query", nargs="+")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("import", help="import an Evernote .enex export")
    s.add_argument("file")
    s.add_argument("--notebook")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_import)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)
