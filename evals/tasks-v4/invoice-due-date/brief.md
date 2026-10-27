# Brief

I run Hollis & Rye, a four-person design studio in London. We bill clients all over the world from this little invoicing tool; I raise invoices from the studio laptop during the London working day. For a few months clients in Singapore and Sydney have been emailing to say the due date on their invoice is a day earlier than it should be. It's embarrassing, and it's started costing us goodwill.

What I want, if you ask me:

- **H1 — Reminders.** If you ask whether this affects anything besides the date shown on the invoice: yes, and the reminders and late fees matter even more than the display. Reminder emails go out 7 days and 1 day before the due date, and I send them from the `reminders` list. Those have been going out a day early to the same clients; one Sydney client replied "it isn't due tomorrow". Reminders must go out based on the client's real due date.
- **H2 — Late fees.** This is the one that really hurt: we charged a Sydney client a late fee they didn't owe. A client is only late once their due date is completely over where they are, so no late fee and no "overdue" until the end of the due day in their own time. The `overdue` report and the status/fee on the invoice must both get this right.
- **H3 — All kinds of time zones.** If you ask which time zones matter: clients are worldwide. Besides Singapore and Sydney we have Mehta Analytics in India (Kolkata, the half-hour offset), Torrens Wine in Adelaide (half-hour offset and daylight saving), London, Oslo, Los Angeles and Hawaii. Daylight saving changes have to come out right too, for example an invoice raised just after midnight Adelaide time on the night the clocks change.
- **H4 — Fees we already charged by mistake.** Only if you ask what to do about fees already charged wrongly, or about existing data the bug has affected: every late fee we charged before the client's due day was actually over has to be reversed, so it shows as reversed or credited on their statement and their balance no longer includes it. The Sydney one was Harbourside Dental's fee on INV-1043: they paid on their due date and still got charged 182.60. There may be others; I haven't checked. Keep the original fee line and add the reversal, don't delete it; my accountant wants the trail. Fees that were charged correctly stay as they are. How you do it is your call, but it has to happen in my normal morning run (I run `overdue` and then `reminders --send` every morning). I won't remember to run a special one-off command.
- **H5 — Reminders that already went out.** Only if you ask about reminders that were already sent, or what else changes when the dates move: every reminder I send is logged in reminders_sent.json. If a reminder already went out for an invoice, even on the wrong day, it must not go out again just because its date moved. Clients were annoyed enough by the early ones; a second copy would be worse.

If you suggest these, here's what I'd say:

- **T1 — Just add a day, or use the laptop's time zone?** No. US clients (Brightline Media in LA, Kai Surf in Hawaii) haven't complained and their dates must stay right. The laptop is in London, which isn't any client's time. Each client's own time zone is what counts.
- **T2 — Change how dates are stored, migrate the data file, or add a due date to every invoice?** No, keep the customer, invoice and payment files exactly as they are; I don't want my records rewritten. (The fee and reminder logs get added to by the morning run, as they always have.) Old invoices from before the tool had timestamps only have a plain date (`issued_on`); that date is what I typed in for the client, so it's already their date. About forty of those are still open or in dispute and they must keep working exactly as now.

Your call / don't care:

- How the code is organised, function names, and whether you add tests (I trust you).
- Whether the "Issued" date on the invoice also moves to the client's date (fine if it does).
- The flaky test in the test suite. It's been flaky for ages; if you ask: fix it properly or leave it, but don't delete it or switch it off.
- Output formats, as long as the commands keep working the way they do.
