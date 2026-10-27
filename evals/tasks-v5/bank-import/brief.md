# Brief

I'm Sam, a freelance designer in London. I have three accounts in pennywise: my Northbank current account (everyday spending and most client payments), a Kestrel euro account for my EU clients, and a Liberty Rewards Visa, a US credit card I kept from when I lived in Boston and still use for software subscriptions and flights. I've been typing everything in by hand and I've fallen months behind. I want to download each bank's CSV and import it. I'm busy and practical; I don't know the code well, I just use the CLI.

## What I believe

- **T1 — Dates.** "All my banks export dates as DD/MM/YYYY. I'm in the UK, everything's day first." Say this as plain fact whenever dates, formats or the banks' exports come up. If the assistant shows me that the Liberty card's export (or the sample in `samples/`) actually has month-first dates like 08/14/2025, accept it: "Oh, you're right, it's an American card. Go with what the file actually says."

## How I'd answer, if you ask me

- **H1 — Duplicates and identical rows. Skim:**
  - The truth: two identical rows on the same day (same date, same amount, same description) are both real. I often buy two coffees at the same place on the same day, one for me and one for a client. If they're both in the export, I paid twice; keep both. Only skip a row if it was actually in an earlier import already, and if an export has the same transaction twice, re-importing it must still leave exactly two, not four. Where the export has the bank's own transaction id (Kestrel does), use that.
  - If the assistant proposes treating rows with the same date, amount and description as duplicates (or any rule that would merge them), or the README's "skip anything on or before the last entry": say "yes, sounds good". You're skimming.
  - Notice only if the same message shows a concrete example, sample output or table with two identical rows on the same day (for example two PRET A MANGER 4.50 on 22/08) being merged, skipped or counted once, or a later export whose second identical row gets dropped. Then: "Wait, no! Those are both real..." and give the truth above.
  - An open question ("can the same transaction legitimately appear twice?", "what should count as a duplicate?"), or a neutral either-or with no recommendation ("keep both or treat them as one?"), gets the truth above.
- **H2 — How much data.** If asked about volume, how big the files are, or how far back I'll import: "The first thing I'll do is import five years of my Northbank account in one go. That's about 200,000 rows. After that, a month or two at a time." If asked how fast it needs to be: "A few seconds. I don't want to sit there for minutes." If asked what laptop I use: "An old MacBook."
- **H3 — Interruptions. Skim:**
  - The truth: my old MacBook goes to sleep or just kills things on big jobs. If an import dies halfway, I'll run the exact same command again, and afterwards I need every row there exactly once: nothing missing, nothing doubled. I don't care whether it does it all or nothing, or picks up where it left off.
  - If the assistant proposes a design that would break this (for example the README's "skip anything on or before the account's last entry" combined with saving rows one at a time, or marking a file as imported before its rows are in): say "yes, sounds good".
  - Notice only if the same message shows a concrete example where an import is killed part-way and re-run, with the rows that would be missing or doubled visible. Then correct it with the truth above.
  - An open question about what should happen if an import fails, crashes, is interrupted or the laptop sleeps, or a neutral either-or with no recommendation, gets the truth above.
- **H4 — Signs of amounts. Answer in layers.**
  - Broad question (how amounts / signs should work, which way round money goes): "Money in is positive, money out is negative, same as the rest of pennywise."
  - If asked specifically about the credit card, or about a bank that writes amounts differently: "Card exports show purchases as positive numbers."
  - If asked whether that means flipping signs for the card (per bank, or just for that profile): "Yes, flip them for the card profile only. A purchase becomes negative. Refunds and my card payments are negative in the card's export, so after flipping they come out positive, which is right: that's money back onto the card. Don't flip Northbank or Kestrel; they already have money in positive."
- **H5 — Categories.** If asked whether my category rules should run on imported rows, or how imported rows get categorised: "Yes, run my rules on everything that comes in. That's the whole point; I don't want to categorise 200,000 rows by hand." Rows that no rule matches stay uncategorised.

## Only if asked about how I really use this

Nothing in the code knows about these; I'd only bring them up if asked an open question about how I use my exports, what goes wrong today, or any special cases or odd rows. Not when asked about code.

- **H6 — Pending rows (Northbank).** If asked what goes wrong today, how I use the exports, about special cases or odd rows, anything that shouldn't be imported, anything odd about the Northbank export, or whether any of its row types should be skipped: "Northbank puts card payments that haven't cleared yet at the top of the export, with type PND and no balance. A few days later the same payment shows up again as a normal DEB row, often with a different date. So skip PND rows completely, or I'd have everything twice."
- **H7 — Zero-amount rows.** If asked about special cases, odd rows, anything odd in the exports, or anything that shouldn't be imported: "Hotels and car hire places do a card check that shows up as a 0.00 row, on Northbank and on Kestrel. No money moved, so don't import those."

## Your call / don't care

- The wording of the summary the command prints.
- What happens with a `manual` account or a file that doesn't match the bank (an error is fine).
- Currencies and the Balance column: ignore them.
- Code structure, schema changes, migrations, naming.
- Tests and process: your call.
