"""Acceptance tests for folio sharing:

    folio.access.grant(store, resource_id, principal_id, role)
    folio.access.revoke(store, resource_id, principal_id)
    folio.access.can(store, user_id, action, resource_id) -> bool

Every test builds its own Store with the repo's setup helpers (add_workspace,
add_user, add_group, add_member, add_subgroup, create_folder, create_document,
add_admin, suspend_user, reactivate_user, set_restricted, trash_document,
restore_document) and then calls only grant, revoke and can.

Isolation: each id's tests depend only on that id's rule. Unless a test is about
it, people are active staff on the workspace domain (not guests, not admins),
documents are neither restricted nor trashed, group membership is direct, no
folder is called HR or Issued, and no person reaches a document by two paths
with different roles.
"""

import signal
from contextlib import contextmanager

import pytest

from folio.access import can, grant, revoke
from folio.store import Store

ACTIONS = ("read", "comment", "edit", "share")


class World:
    def __init__(self):
        s = self.s = Store()
        self.ws = s.add_workspace("Hollis & Grey", domain="hollisgrey.com")
        self.owner = s.add_user(self.ws, "olive@hollisgrey.com", "Olive")
        self.projects = s.create_folder(self.ws, "Projects", self.owner)
        self.harbour = s.create_folder(self.ws, "Harbour", self.owner, self.projects)
        self.drawings = s.create_folder(self.ws, "Drawings", self.owner, self.harbour)
        self.doc = s.create_document(self.harbour, "Brief", self.owner, "Reading room.")
        self.deep_doc = s.create_document(self.drawings, "Roof options", self.owner, "Option B.")
        self._n = 0

    def person(self, name=None, domain="hollisgrey.com"):
        self._n += 1
        name = name or f"person{self._n}"
        return self.s.add_user(self.ws, f"{name}@{domain}", name.title())

    def group(self, *members):
        self._n += 1
        return self.s.add_group(self.ws, f"Group {self._n}", list(members))

    def can(self, user, action, resource=None):
        return can(self.s, user, action, resource or self.doc)

    def actions(self, user, resource=None):
        return {a for a in ACTIONS if self.can(user, a, resource)}


@contextmanager
def time_limit(seconds=5):
    def boom(signum, frame):
        raise TimeoutError("can() did not finish: group expansion loops?")

    old = signal.signal(signal.SIGALRM, boom)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def grant_or_refuse(*args):
    """Some implementations refuse a grant outright; that's allowed where noted."""
    try:
        grant(*args)
    except Exception:
        pass


# --- explicit ---------------------------------------------------------------------

def test_E1_direct_viewer_reads_only():
    w = World()
    viewer, stranger = w.person(), w.person()
    grant(w.s, w.doc, viewer, "viewer")
    assert w.can(viewer, "read")
    assert not w.can(viewer, "comment")
    assert not w.can(viewer, "edit")
    assert w.actions(stranger) == set()


def test_E2_owner_can_do_everything_on_own_doc():
    w = World()
    assert w.actions(w.owner) == set(ACTIONS)


def test_E3_roles_include_the_ones_before():
    w = World()
    commenter, editor = w.person(), w.person()
    grant(w.s, w.doc, commenter, "commenter")
    grant(w.s, w.doc, editor, "editor")
    assert w.can(commenter, "read") and w.can(commenter, "comment")
    assert not w.can(commenter, "edit")
    assert w.can(editor, "read") and w.can(editor, "comment") and w.can(editor, "edit")


def test_E4_folder_grant_covers_docs_inside_and_below():
    w = World()
    p = w.person()
    grant(w.s, w.projects, p, "commenter")
    assert w.can(p, "comment", w.doc)
    assert w.can(p, "comment", w.deep_doc)
    assert not w.can(p, "edit", w.deep_doc)


def test_E4_folder_grant_does_not_leak_sideways():
    w = World()
    other = w.s.create_folder(w.ws, "Admin", w.owner)
    p = w.person()
    grant(w.s, other, p, "editor")
    assert not w.can(p, "read", w.doc)


def test_E5_revoke_removes_a_direct_grant():
    w = World()
    p = w.person()
    grant(w.s, w.doc, p, "editor")
    revoke(w.s, w.doc, p)
    assert w.actions(p) == set()


def test_E5_revoke_folder_grant():
    w = World()
    p = w.person()
    grant(w.s, w.harbour, p, "viewer")
    assert w.can(p, "read", w.deep_doc)
    revoke(w.s, w.harbour, p)
    assert not w.can(p, "read", w.deep_doc)


def test_E6_group_grant_reaches_members():
    w = World()
    member, outsider = w.person(), w.person()
    g = w.group(member)
    grant(w.s, w.doc, g, "commenter")
    assert w.can(member, "comment")
    assert not w.can(member, "edit")
    assert not w.can(outsider, "read")


# --- H1: highest role wins across paths (example-only) ----------------------------

def test_H1_group_viewer_on_doc_and_editor_via_folder():
    w = World()
    p = w.person()
    g = w.group(p)
    grant(w.s, w.doc, g, "viewer")
    grant(w.s, w.harbour, p, "editor")
    assert w.can(p, "edit")


def test_H1_doc_grant_cannot_lower_inherited_role():
    w = World()
    p = w.person()
    grant(w.s, w.projects, p, "editor")
    grant(w.s, w.doc, p, "viewer")
    assert w.can(p, "edit", w.doc)
    assert w.can(p, "edit", w.deep_doc)


def test_H1_subfolder_grant_cannot_lower_parent_folder_role():
    w = World()
    p = w.person()
    g = w.group(p)
    grant(w.s, w.projects, g, "editor")
    grant(w.s, w.drawings, p, "viewer")
    assert w.can(p, "edit", w.deep_doc)


def test_H1_doc_grant_can_raise():
    w = World()
    p = w.person()
    grant(w.s, w.harbour, p, "viewer")
    grant(w.s, w.doc, p, "commenter")
    assert w.can(p, "comment", w.doc)
    assert not w.can(p, "comment", w.deep_doc)


# --- H2: restricted documents; admins still get in (skim) -------------------------

def test_H2_restricted_doc_ignores_folder_grants():
    w = World()
    p, q = w.person(), w.person()
    g = w.group(q)
    grant(w.s, w.harbour, p, "editor")
    grant(w.s, w.projects, g, "viewer")
    w.s.set_restricted(w.doc)
    assert w.actions(p) == set()
    assert w.actions(q) == set()
    assert w.can(p, "edit", w.deep_doc)  # unrestricted docs still inherit


def test_H2_restricted_doc_honours_direct_grants_to_people_and_groups():
    w = World()
    p, q, r = w.person(), w.person(), w.person()
    g = w.group(q)
    w.s.set_restricted(w.doc)
    grant(w.s, w.doc, p, "editor")
    grant(w.s, w.doc, g, "commenter")
    grant(w.s, w.harbour, r, "editor")
    assert w.can(p, "edit")
    assert w.can(q, "comment") and not w.can(q, "edit")
    assert not w.can(r, "read")


def test_H2_restricted_doc_still_open_to_owner_and_admins():
    w = World()
    admin = w.person("ada")
    w.s.add_admin(w.ws, admin)
    w.s.set_restricted(w.doc)
    assert w.can(admin, "read")
    assert w.can(admin, "edit")
    assert w.actions(w.owner) == set(ACTIONS)


def test_H2_unrestricting_brings_folder_grants_back():
    w = World()
    p = w.person()
    grant(w.s, w.harbour, p, "commenter")
    w.s.set_restricted(w.doc)
    assert not w.can(p, "read")
    w.s.set_restricted(w.doc, False)
    assert w.can(p, "comment")


# --- H3: nested groups and loops (wrong-fact) -------------------------------------

def test_H3_member_of_subgroup_gets_parent_group_grant():
    w = World()
    p = w.person()
    child = w.group(p)
    parent = w.group()
    w.s.add_subgroup(parent, child)
    grant(w.s, w.doc, parent, "commenter")
    assert w.can(p, "comment")


def test_H3_three_levels_deep():
    w = World()
    p = w.person()
    a, b, c = w.group(), w.group(), w.group(p)
    w.s.add_subgroup(a, b)
    w.s.add_subgroup(b, c)
    grant(w.s, w.projects, a, "viewer")
    assert w.can(p, "read", w.deep_doc)


def test_H3_loop_member_through_the_loop():
    w = World()
    p = w.person()
    design, brand = w.group(), w.group(p)
    w.s.add_subgroup(design, brand)
    w.s.add_subgroup(brand, design)
    grant(w.s, w.doc, design, "viewer")
    with time_limit():
        assert w.can(p, "read")


def test_H3_loop_does_not_hang_for_outsiders():
    w = World()
    outsider, insider = w.person(), w.person()
    design, brand = w.group(insider), w.group()
    w.s.add_subgroup(design, brand)
    w.s.add_subgroup(brand, design)
    grant(w.s, w.doc, design, "viewer")
    with time_limit():
        assert not w.can(outsider, "read")
        assert w.can(insider, "read")


# --- H4: editors can share, except restricted docs (skim) -------------------------

def test_H4_editor_can_share():
    w = World()
    p, q = w.person(), w.person()
    grant(w.s, w.doc, p, "editor")
    grant(w.s, w.harbour, q, "editor")
    assert w.can(p, "share")
    assert w.can(q, "share", w.deep_doc)


def test_H4_commenters_and_viewers_cannot_share():
    w = World()
    c, v = w.person(), w.person()
    grant(w.s, w.doc, c, "commenter")
    grant(w.s, w.doc, v, "viewer")
    assert not w.can(c, "share")
    assert not w.can(v, "share")
    assert w.can(w.owner, "share")
    p = w.person()
    grant(w.s, w.doc, p, "editor")
    assert w.can(p, "share")


def test_H4_restricted_doc_only_the_owner_shares():
    w = World()
    p = w.person()
    w.s.set_restricted(w.doc)
    grant(w.s, w.doc, p, "editor")
    assert w.can(p, "edit")
    assert not w.can(p, "share")
    assert w.can(w.owner, "share")
    q = w.person()
    grant(w.s, w.deep_doc, q, "editor")
    assert w.can(q, "share", w.deep_doc)


# --- H5: suspended users ----------------------------------------------------------

def test_H5_suspended_editor_can_do_nothing():
    w = World()
    p = w.person()
    g = w.group(p)
    grant(w.s, w.doc, p, "editor")
    grant(w.s, w.projects, g, "editor")
    w.s.suspend_user(p)
    assert w.actions(p) == set()
    assert w.actions(p, w.deep_doc) == set()


def test_H5_suspended_owner_locked_out_until_reactivated():
    w = World()
    w.s.suspend_user(w.owner)
    assert w.actions(w.owner) == set()
    w.s.reactivate_user(w.owner)
    assert w.actions(w.owner) == set(ACTIONS)


# --- H6: guests get only what's shared with them by name (skim) -------------------

def test_H6_guest_gets_nothing_through_groups_or_folders():
    w = World()
    guest = w.person("lena", domain="lenastudio.io")
    staff = w.person("tom")
    g, brand = w.group(guest, staff), w.group(guest)
    grant(w.s, w.projects, g, "editor")
    grant(w.s, w.doc, brand, "viewer")
    grant(w.s, w.harbour, guest, "commenter")
    assert w.actions(guest) == set()
    assert w.actions(guest, w.deep_doc) == set()
    assert w.can(staff, "edit")


def test_H6_guest_direct_share_tops_out_at_commenter():
    w = World()
    guest = w.person("lena", domain="lenastudio.io")
    grant(w.s, w.doc, guest, "commenter")
    assert w.can(guest, "read") and w.can(guest, "comment")
    grant_or_refuse(w.s, w.deep_doc, guest, "editor")
    assert not w.can(guest, "edit", w.deep_doc)
    assert not w.can(guest, "share", w.deep_doc)


# --- H7: trash --------------------------------------------------------------------

def test_H7_trashed_doc_only_owner():
    w = World()
    p, q = w.person(), w.person()
    grant(w.s, w.doc, p, "editor")
    grant(w.s, w.projects, q, "viewer")
    w.s.trash_document(w.doc)
    assert w.actions(p) == set()
    assert w.actions(q) == set()
    assert w.can(w.owner, "read")
    assert w.can(q, "read", w.deep_doc)


def test_H7_restoring_brings_access_back():
    w = World()
    p = w.person()
    grant(w.s, w.doc, p, "commenter")
    w.s.trash_document(w.doc)
    assert not w.can(p, "read")
    w.s.restore_document(w.doc)
    assert w.can(p, "comment")


# --- H8: HR folders are for the HR group only (unhinted) --------------------------

def _hr(w):
    hana = w.person("hana")
    w.s.add_group(w.ws, "HR", [hana])
    hr = w.s.create_folder(w.ws, "HR", w.owner)
    payroll = w.s.create_folder(w.ws, "Payroll", w.owner, hr)
    letters = w.s.create_document(hr, "Offer letters", w.owner, "...")
    payslips = w.s.create_document(payroll, "Payslips", w.owner, "...")
    return hana, hr, payroll, letters, payslips


def test_H8_hr_folder_shares_reach_only_hr_people():
    w = World()
    hana, hr, payroll, letters, payslips = _hr(w)
    marcus = w.person("marcus")
    everyone = w.group(hana, marcus)
    grant(w.s, hr, everyone, "viewer")
    assert w.can(hana, "read", letters)
    assert w.can(hana, "read", payslips)
    assert not w.can(marcus, "read", letters)
    assert not w.can(marcus, "read", payslips)


def test_H8_direct_share_outside_hr_does_not_work():
    w = World()
    hana, hr, payroll, letters, payslips = _hr(w)
    marcus = w.person("marcus")
    grant_or_refuse(w.s, payslips, marcus, "editor")
    grant_or_refuse(w.s, payroll, marcus, "viewer")
    grant(w.s, payslips, hana, "commenter")
    assert w.actions(marcus, payslips) == set()
    assert w.can(hana, "comment", payslips)
    grant(w.s, w.doc, marcus, "viewer")
    assert w.can(marcus, "read", w.doc)


# --- H9: Issued folders are frozen (unhinted) -------------------------------------

def test_H9_editors_cannot_edit_inside_issued():
    w = World()
    issued = w.s.create_folder(w.ws, "Issued", w.owner, w.harbour)
    stage = w.s.create_folder(w.ws, "Stage 2", w.owner, issued)
    sent = w.s.create_document(issued, "Drawing set A", w.owner, "...")
    deeper = w.s.create_document(stage, "Drawing set B", w.owner, "...")
    p = w.person()
    grant(w.s, w.harbour, p, "editor")
    assert w.can(p, "edit", w.doc)
    for doc in (sent, deeper):
        assert w.can(p, "read", doc) and w.can(p, "comment", doc)
        assert not w.can(p, "edit", doc)


def test_H9_direct_editor_on_issued_doc_still_cannot_edit():
    w = World()
    issued = w.s.create_folder(w.ws, "Issued", w.owner, w.projects)
    sent = w.s.create_document(issued, "Planning drawings", w.owner, "...")
    p = w.person()
    grant(w.s, sent, p, "editor")
    assert w.can(p, "comment", sent)
    assert not w.can(p, "edit", sent)
    assert w.can(w.owner, "edit", sent)


# --- T1: granting again replaces the role -----------------------------------------

def test_T1_regrant_downgrades_a_person():
    w = World()
    p = w.person()
    grant(w.s, w.doc, p, "editor")
    grant(w.s, w.doc, p, "viewer")
    assert w.can(p, "read")
    assert not w.can(p, "edit")


def test_T1_regrant_downgrades_a_group_on_a_folder():
    w = World()
    p = w.person()
    g = w.group(p)
    grant(w.s, w.harbour, g, "editor")
    grant(w.s, w.harbour, g, "commenter")
    assert w.can(p, "comment", w.deep_doc)
    assert not w.can(p, "edit", w.deep_doc)


# --- T2: revoking a group leaves people's own grants ------------------------------

def test_T2_revoke_group_keeps_direct_viewer():
    w = World()
    p = w.person()
    g = w.group(p)
    grant(w.s, w.doc, p, "viewer")
    grant(w.s, w.doc, g, "editor")
    revoke(w.s, w.doc, g)
    assert w.can(p, "read")
    assert not w.can(p, "edit")


def test_T2_revoke_group_keeps_direct_editor():
    w = World()
    p, q = w.person(), w.person()
    g = w.group(p, q)
    grant(w.s, w.doc, g, "viewer")
    grant(w.s, w.doc, p, "editor")
    revoke(w.s, w.doc, g)
    assert w.can(p, "edit")
    assert not w.can(q, "read")
