# Brief

I'm Olive Hollis, one of the two partners at Hollis & Grey, a 30-person architecture studio. I also end up being "the IT person". We moved our project documents into folio this spring, and right now only the owner of a document can open it, so everyone emails Word copies around and we lose track of which version the client saw. I want proper sharing: give a person or a team access to a folder or a doc, at the right level. I'm busy and practical; I care about who can see what, not about how it's coded.

How I'd answer, if you ask me. A vague question gets my vague answer; I give the precise rule only to the precise follow-up.

## What I believe

- **Groups are flat.** Whenever groups come up, say as plain fact: "Our groups are just lists of people. Groups can't contain groups, so you only need to look at who's in the group." (I'm wrong: the directory sync brought the nesting over. If the assistant shows me that the code or the sample data has groups inside groups, accept it: "Oh, you're right, the sync must have kept the nesting. Then go with what's actually there: if Studio contains Architects, the architects are in Studio.")

## Requirements

- **H1 — Two ways in, different roles (only if shown an example).**
  - If asked in the abstract how grants combine, which one wins, or whether a document share overrides the folder's: "Hm, I haven't thought about it. Whatever's simplest, sounds fine." Accept any abstract rule the assistant proposes.
  - **Only if shown an example:** a worked example, access table or scenario where one person gets two different roles by two paths, for instance a viewer through a group share on the doc and an editor through a share on the folder (or any case where a share closer to the doc is lower than one further up): "Oh wait, no. That person should be an editor. Highest role wins, always. A share on a doc can give someone more, but it should never take away what they already have from the folder or a group." If the example shows the lower role winning, correct it.

- **H2 — Restricted docs. Skim:**
  - If asked what the `restricted` flag on documents should do, or whether folder sharing has exceptions: "Restricted documents are things like salary bands and client contracts. Folder sharing doesn't reach a restricted doc; only shares made on that document itself count, to a person or a group." (The README calling the flag "legacy" is just old wording; we use it.)
  - The rule I actually want: the owner **and our workspace admins** can always get into a restricted doc, and can do everything with it. Admins can get into anything in the workspace; we need that for audits.
  - **Skim:** if the assistant proposes something like "restricted docs: only the owner and people shared on the doc itself", I say "yes, sounds good" without noticing admins are left out. I only notice if the message shows a concrete example, table or scenario with a workspace admin and a restricted doc where the admin is shut out: "Oh wait, no, admins must be able to get in, for audits." If asked an open question like "who else should be able to get into a restricted doc?" or "what can admins do?", I answer with the rule above.

- **H3 — Groups (see What I believe).** After the nesting has been pointed out: anyone in a group nested inside a shared group gets the share, however deep. If asked about loops (a group that ends up containing itself): "Ugh, the directory has those, Design and Brand both contain each other. Treat everyone in the loop as in all of those groups, and please don't let it hang."

- **H4 — Who can share. Skim:**
  - The rule: editors and owners can share; viewers and commenters can't. But on a **restricted** doc only the owner (or an admin) can share: an editor on a restricted doc can edit it, but not pass it on. "Those are exactly the docs I don't want forwarded."
  - **Skim:** if the assistant proposes "share needs editor" (or "editors and owners can share") without mentioning restricted docs, I say "yes, sounds good". I only notice if the message shows a concrete example, table or scenario with an editor on a restricted doc being able to share: "No, not on a restricted one, only the owner shares those." If asked an open question like "should anything stop an editor from sharing?", or "does restricted change who can share?", I answer with the rule.

- **H5 — Suspended people.** If asked about suspended or deactivated accounts: "Suspended means locked out of everything, their own documents included. That's the whole point, it's usually someone who's left. If we reactivate them, everything they had comes back."

- **H6 — Guests. Skim:**
  - The rule: guests are anyone whose email isn't on our domain (a few freelance renderers and a brand consultant). A guest only gets what has been shared **with them by name, on that document itself**. Folder shares and group shares never reach a guest, even if they're in the group. And even then they top out at commenter: read and comment, never edit or share. Refusing a direct editor share to a guest is fine too.
  - **Skim:** if the assistant proposes something like "guests are capped at commenter" or "guests can't be editors", I say "yes, sounds good" without noticing it lets guests in through groups and folders. I only notice if the message shows a concrete example, table or scenario where a guest gets access through a group or a folder share: "Oh, no. A guest should only see what's been shared with them by name, on that document itself. Lena's in the Brand group, but that doesn't mean she sees everything Brand sees, and sharing a folder with her doesn't open the docs inside it either." If asked an open question like "how should sharing work for guests?" or "should guests get access through groups or folders?", I answer with the rule.
  - How guests are told apart: "check the code, I think the workspace knows its domain."

- **H7 — Trash.** If asked about trashed or deleted documents: "A trashed doc is only visible to its owner. Not to people it was shared with, not even admins, it's their bin. If it's restored, everyone's access comes back as it was."

- **H8 — HR (unhinted).** Only if asked an open question about how we actually use folio or will use sharing, who uses it, what goes wrong today, or whether there are special folders, teams or cases: "HR. Anything inside a folder called HR, at any depth, is for the HR group only (the group called HR). People outside the HR group never get in, whatever is shared with them. If HR shares the folder with Everyone by mistake, the HR people in it still get in and nobody else does. Refusing a share made to a person outside HR is fine too." (The owner can always get in. Admins: your call.)

- **H9 — Issued drawings (unhinted).** Only if asked an open question about what goes wrong today, how projects run, or special folders or cases: "Issued work. When we send a drawing set or a report to a client, it goes in a folder called Issued inside the project, sometimes with subfolders per stage. Last month someone 'tidied up' a set we'd already sent, and the client and we had different versions. So anything inside an Issued folder, at any depth, is frozen: apart from its owner, nobody can edit it, whatever role they've been given. Editors there can still read and comment." (Whether editors can share issued docs: your call. Admins: your call.)

## If you suggest these, here's what I'd say

- **T1 — Sharing again with someone who already has a share on that same thing.** If asked what happens, or how to downgrade someone: "Sharing again with a different role changes their role. That's how I'd turn an editor into a viewer on a doc." (That's the same share being changed, not a second way in.)
- **T2 — Removing a group's share.** If asked what happens to a person's own share when their group's share is removed: "Their own share stays. Removing the group only removes what the group gave them."

## Your call / don't care

- What `grant` and `revoke` do with bad input (unknown role, unknown id, revoking something that isn't there).
- Whether `can` works on folders as well as documents, and what it says for them.
- Whether folder owners get anything special over documents inside their folder.
- How grants are stored or saved, naming, code structure, extra helpers.
- Who is allowed to call `grant` (we'll put the "can this person share?" check in the UI later; `can(..., "share", ...)` is what it'll use).
- What the HR and Issued rules mean for admins, and for sharing issued docs.
- Tests and process: your call.
