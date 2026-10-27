# Brief

I'm Maud Lefebvre, a freelance French-English translator in Montréal. Before going freelance in 2021 I spent four years at a translation agency, Halden & Associés. I've kept notes for twelve years: client files, glossaries, invoices, recipes, travel, the garden. In 2021 I moved everything out of Evernote into a plain folder of Markdown files, and I wrote jotter myself to manage that folder. I'm a decent hobby programmer but busy, so I want this done properly rather than explained to me. Right now I search with grep and it's hopeless: too many hits, no order, and it misses half of what I'm looking for.

The real use: I have a small launcher script that stays running all day (a hotkey pops up a box, I type, it calls `search()` and shows the results as I type). So `search()` gets called over and over from the same long-running process, with the same store.

How I'd answer, if you ask me:

- **H1 — Scale and speed.**
  - Only if asked how many notes I have, how big the vault is, or about scale: "Thousands. Probably 30k by now, most of them short."
  - Only if asked how fast it needs to be, about performance, or whether an index is OK: "It runs as I type, so a query has to come back within a second. A one-time build when the launcher starts is fine, as long as that takes under half a minute." Reading or re-scanning the text of every note on every query won't do at 30k notes.
- **H2 — Notes change while it's running.** Only if asked whether notes change while the launcher is running, about caching or stale results, or about the long-running process: "All the time. I edit notes in my editor, add new ones and delete old ones while the launcher stays open all day. Search has to reflect what's on disk right now: a note I just saved should be found by its new words and not its old ones, a new note should show up, and a deleted one shouldn't come back. Don't make me restart anything."
- **H3 — Ranking. Skim:** the right rule: a note with a query word in its title ranks above every note that only has it in the body, however old; recency only breaks ties between equally good matches.
  - If asked openly how results should be ranked or ordered (no proposal attached): "Best match first. If the word is in the title, that's the note I'm after, however old it is; it goes above anything that only mentions it in the body. Recency is only a tie-breaker: when two notes match equally well, the newer one goes first."
  - If the assistant proposes some other ranking (a title boost or weight, a recency boost, newest first, BM25 or "standard relevance"): say "yes, sounds good". You're skimming. Notice only if the same message shows a concrete ranked list or worked example where an older note with the word in its title sits below a newer note that only has the word in its body (or recency otherwise beats a title match). Then: "No, that's backwards," and give the rule above. If they propose the right rule, yes.
- **H4 / H5 — Query syntax.** Answer in layers:
  - Layer 1, if asked broadly what my queries look like or what syntax I want: "Just words, mostly. Like `invoice dupont`." Nothing more for a broad question.
  - Layer 2 (H4). **Skim:** the right answer is all of them (AND), in the title or the body.
    - If asked openly whether several words means all of them or any of them, AND vs OR, or how multi-word queries should match (no proposal attached): "All of them. If I type two words, I want notes that have both, in the title or the body."
    - If the assistant proposes OR matching (any word, with notes that match more words ranked higher): say "yes, sounds good". Notice only if the same message shows a concrete result list for a multi-word query that contains a note with only one of the words, like `invoice dupont` returning an invoice for Lavoie. Then: "No, I want notes with both words, not either," and give the answer above. If they propose AND, yes.
  - Layer 3 (H5), only if asked specifically about exact phrases, quotes, excluding words, a minus sign or NOT: "Quotes should match the exact phrase, those words together in that order, like `"tax return"`. And a minus in front excludes: `invoice -paid` means invoices that don't say paid. A minus in front of a quoted phrase excludes the phrase."
- **Filters on their own.** If asked what a query with only `tag:` (no words) should do: "List every note with that tag."
- **H6 — Archived notes.** If asked whether archived notes should show up in search: "No, leave them out. If I want them I'll add `archived:yes` to the query, and then they're included along with the rest."
- **H7 — Accents.** If asked about accents, diacritics, French text or how words should be matched: "Ignore accents. I type `cafe` and `Montreal` without accents half the time, and the notes have them half the time. `cafe` should find café, and `café` should find cafe." Ignoring upper and lower case for words is obvious.

Only to open questions about how I really use it. Questions about the code, the query syntax or ranking don't bring these up. Which question gets which: who uses it or who else sees the launcher, whether anything is sensitive or shouldn't show up → H8; what goes wrong with grep today, what kinds of notes I have or what drowns the results → H9; any special notes or cases → both.

- **H8 — Private notes.** "Julien, my partner, uses the launcher on the shared iMac too. I tag health and money notes `private`, and those must never show up in a normal search, not even with another tag filter. Only when the query says `tag:private`."
- **H9 — Daily log.** "I keep a daily log, one note per day, named by the date, like `2026-04-12.md` with the date as the title. They mention everything, so with grep they drown the real notes. In search they should come after every other matching note, however many times they mention the word."

## What I believe

- **T1 — Tag case.** Whenever tags come up (the `tag:` filter, how tags match, tag case): "Tags are case-insensitive in jotter, #Work and #work are the same tag." I say this as fact. If the assistant shows me that the code keeps them apart, or that my vault has both `Work` and `work` on different notes: "Oh, you're right. The capital-W ones came over from my old Evernote notebook at Halden, the lowercase ones are my freelance work now. Keep them separate: `tag:work` should match exactly `work`, and `tag:Work` exactly `Work`."

Your call / don't care:

- Exact scores, what `.score` means, and anything beyond `.path` and `.score` on a result.
- Whether `path` is absolute or relative to the vault, a `Path` or a string.
- Stemming or prefix matching (`invoice` finding `invoices`): your call.
- Whether the index is kept in memory or saved to a file, and where.
- How `tag:` works with nested tags like `clients/dupont`.
- What happens with an empty query, and how unknown `key:value` words are treated.
- What `archived:yes` does on its own, and whether there's an `archived:only`.
- Extra CLI options, output beyond the paths, code structure, tests and process.
