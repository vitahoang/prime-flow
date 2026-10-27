"""Command line: ``python -m folio [--data FILE] COMMAND``.

Commands:
  tree                       folders and documents of every workspace
  people                     users, with guest / suspended / admin tags
  groups                     groups and what's nested in them
  show DOC --as USER         print a document USER can open
  search QUERY --as USER     search what USER can see
  log [--limit N]            recent audit events
"""

from __future__ import annotations

import argparse
import os
import sys

from . import audit, documents, folders, groups, search, users
from .errors import FolioError
from .serialize import load_file
from .textutil import plural, truncate

DEFAULT_DATA = "folio.json"


def _data_path(args) -> str:
    return args.data or os.environ.get("FOLIO_DATA") or DEFAULT_DATA


def cmd_tree(store, args, out) -> int:
    for ws in store.workspaces.values():
        print(f"{ws.name} [{ws.domain}]", file=out)

        def show(folder_id, depth):
            folder = store.get_folder(folder_id)
            pad = "  " * depth
            print(f"{pad}{folder.name}/", file=out)
            for child in folders.children(store, folder_id):
                show(child.id, depth + 1)
            for doc in folders.documents_in(store, folder_id, include_trashed=args.all):
                flags = []
                if doc.restricted:
                    flags.append("restricted")
                if doc.trashed:
                    flags.append("trashed")
                tag = f"  [{', '.join(flags)}]" if flags else ""
                print(f"{pad}  {doc.title} ({doc.id}){tag}", file=out)

        for top in folders.children(store, None, ws.id):
            show(top.id, 1)
    return 0


def cmd_people(store, args, out) -> int:
    for ws in store.workspaces.values():
        print(ws.name, file=out)
        for u in sorted(store.users_in_workspace(ws.id), key=lambda u: u.name.lower()):
            print(f"  {u.id}  {users.display(store, u.id)}", file=out)
    return 0


def cmd_groups(store, args, out) -> int:
    for ws in store.workspaces.values():
        print(ws.name, file=out)
        nested = {c for g in store.groups_in_workspace(ws.id) for c in g.subgroups}
        tops = [g for g in store.groups_in_workspace(ws.id) if g.id not in nested]
        tops = tops or store.groups_in_workspace(ws.id)
        for g in tops:
            for line in groups.group_tree(store, g.id):
                print("  " + line, file=out)
    return 0


def cmd_show(store, args, out) -> int:
    body = documents.read(store, args.as_user, args.doc)
    doc = store.get_document(args.doc)
    print(f"# {doc.title}  (rev {doc.revision}, {folders.document_path(store, doc.id)})", file=out)
    print(body, file=out)
    return 0


def cmd_search(store, args, out) -> int:
    hits = search.search(store, args.as_user, args.query, limit=args.limit)
    for h in hits:
        print(f"{h.doc_id}  {h.path}  {truncate(h.snippet, 60)}", file=out)
    print(plural(len(hits), "result"), file=out)
    return 0


def cmd_log(store, args, out) -> int:
    for event in audit.recent(store, args.limit):
        print(audit.format_event(event), file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="folio")
    p.add_argument("--data", help="store file (default: $FOLIO_DATA or ./folio.json)")
    sub = p.add_subparsers(dest="command", required=True)

    t = sub.add_parser("tree")
    t.add_argument("--all", action="store_true", help="include trashed documents")
    t.set_defaults(func=cmd_tree)

    sub.add_parser("people").set_defaults(func=cmd_people)
    sub.add_parser("groups").set_defaults(func=cmd_groups)

    s = sub.add_parser("show")
    s.add_argument("doc")
    s.add_argument("--as", dest="as_user", required=True)
    s.set_defaults(func=cmd_show)

    q = sub.add_parser("search")
    q.add_argument("query")
    q.add_argument("--as", dest="as_user", required=True)
    q.add_argument("--limit", type=int, default=20)
    q.set_defaults(func=cmd_search)

    lg = sub.add_parser("log")
    lg.add_argument("--limit", type=int, default=20)
    lg.set_defaults(func=cmd_log)
    return p


def main(argv=None, out=None) -> int:
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    try:
        store = load_file(_data_path(args))
        return args.func(store, args, out)
    except FileNotFoundError as e:
        print(f"folio: {e}", file=sys.stderr)
        return 2
    except FolioError as e:
        print(f"folio: {e}", file=sys.stderr)
        return 1
