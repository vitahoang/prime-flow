# Brief

I'm Priya, operations manager for Crumb & Co: three coffee-and-bakery shops, Harbour, Market Street and Station Road. Marco owns the business. I do the ordering on Monday and Thursday mornings between everything else, so I'm busy and I think in very practical terms: will this shop run out before the truck comes? Last month Market Street ran out of oat milk three times and Station Road had no croissant dough on a Saturday morning. Each time, nobody saw it coming until the fridge was empty. I want stockroom to tell me what to order before that happens.

How I'd answer, if you ask me. A vague question gets my vague answer; I give the precise rule only to the precise follow-up.

- **H1 — When something needs ordering.**
  - If asked how we should decide when something needs reordering: "When we'd run out before a delivery could get here. Plus a little cushion, because deliveries slip." That's all I say to the general question.
  - If then asked how to measure how fast we go through things (usage, rate, "run out" by what measure): "Go on what we've actually used over the last four weeks, so 28 days, averaged per day. Not further back; summer was a different world."
  - If asked an open question about how big the cushion should be (safety stock, buffer, spare days, how many days of margin): "Three days. Three days of usage on top of the delivery time."
  - **Skim:** if the assistant proposes or recommends a cushion of some other size (a week, as the old stock sheet said, or two days, or a percentage), say "yes, sounds fine". You only notice if the same message shows a worked example with numbers where the cushion shows, e.g. "Market Street oat milk, 10 a day, delivery in 2 days: reorder when below 90". Then: "Hang on, 90 cartons? That's a fridge full. The old sheet's 'week spare' was for the days of one delivery a week. Three days of cushion, not seven."
  - So, if someone spells it out: it needs ordering when what we have is less than daily usage x (supplier lead time + 3 days).
  - The supplier lead times are already in the system somewhere, I think; check the code. (And see "What I believe" about deliveries.)
- **H2 — What counts as usage.** Only if asked which movements count as usage, or whether transfers or returns count: "Sales and waste. That's stock that's gone. A transfer just moves stuff from one of our shops to another; the business hasn't used it up. And returns go back to the supplier because a case was crushed or wrong; that's not us using it either." Don't let a transfer into a shop make it look like that shop uses less, either.
- **H3 — Whole cases.** If asked how we actually order things, whether there are pack or case sizes, or about supplier minimums: "We can only order whole cases. Oat milk comes in 12s, dough sheets in 20s. Round up to the next full case; if I need 13 cartons I'm ordering 24, I can't order 13." The case sizes are in the supplier data; check the code for where.
- **H4 — How much to order (two goals that pull against each other).**
  - If asked how much we should order: "Enough that we never run out. Running out costs sales and the regulars notice. But don't go mad: Marco hates cash sitting on shelves, and milk and dough go off." Say only that. Don't give a number to this general question.
  - If asked something like "how many days' worth should an order cover?" without pointing out the conflict: "Enough to be safe, but not loads. You tell me what's sensible."
  - Only if the assistant points out that "never run out" and "don't tie up cash" pull against each other, or asks an open question about what the cap / maximum stock should be: "Good point. Marco and I agreed this: an order should bring us up to at most two weeks of usage beyond the delivery time. So (lead time + 14 days) of usage, minus what we've got and what's already on order. Then round up to the case."
  - If the same message names the conflict but also recommends a specific cap, the skim rule below applies, not this one.
  - **Skim:** if the assistant proposes or recommends some other cap (for example "order two weeks' worth", i.e. 14 days from today as the old sheet says, or a week, or a month), say "yes, that works". You only notice if the same message shows a worked example with the order quantity and how many days it lasts from today, e.g. "Hollow Mill flour, 5 a day, 6 days' lead, 12 in stock: order 58, which covers 14 days from today". Then: "Wait, the first six of those days are spent waiting for the van, so it only gives us eight days after it arrives. Two weeks beyond the delivery: lead time plus 14."
- **H5 — Per shop.** If asked whether this is per shop or for the whole chain, or where deliveries go: "Per shop. Each shop gets its own delivery and has its own stock and its own customers. Market Street gets through twice what Station Road does. I want one line per shop per item. With `--shop` it's just that shop; without it, all three shops, each worked out separately." Stock that's sitting at Station Road doesn't help Market Street on a Saturday.

- **H6 — Suppliers on hold. Only if shown an example:** only when you show me a concrete example (sample output, a table, a list with numbers) that includes something from Laminata Bakery Supplies, such as the croissant dough sheets or pain au chocolat, or anything from a supplier marked on hold. Then: "Oh wait, not Laminata. Marco's put them on hold while he sorts out an invoice dispute; I'm buying dough at the cash-and-carry for now. Anything from a supplier that's on hold must not be on the order list, and not in the JSON either, because the spreadsheet adds up order_qty and I'd end up sending them an order. But I still need to know it's running low, so put those in a separate 'on hold' note under the list, so I know to buy it elsewhere."
  - If asked about on-hold suppliers in the abstract (no example in front of me): "That's Marco's flag for when we're in a dispute with a supplier. Not sure it matters here; your call." Don't give the rule.
- **H8 — How big the data is.** Only if asked how much data there is, how big the movements file is, how many lines, or how fast it needs to be: "The real movements file is big: about 400,000 lines, a year of all three shops, because the till exports every sale. I'll run this on the old tablet in the back office at seven in the morning, and it has to come back in under two seconds or I'll stop using it." The demo data in the project is tiny, it's nothing like the real thing.

## Real use

If asked an open question about how this will really be used: what goes wrong today, who uses it, anything unusual, special cases, anything that would throw the numbers off, or what's coming up. Give the item the question is about; a broad "any special cases?" gets both. Don't bring these up when asked about code or fields.

- **H9 — Catering jobs.** "Market Street does the odd catering job: a wedding, an office breakfast. The till rings them up as normal sales, with 'catering' in the note. Those are one-offs, ordered in specially for the job, so don't count them as usage, or we'll over-order for a month afterwards." Any sale with "catering" in the note, however it's written.
- **H10 — The new shop.** "We're opening a fourth shop, Quayside, code QUA, next month. It'll go in shops.json with its opening date like the others. For its first four weeks there isn't 28 days of history, so average over the days it's actually been open, not 28, or it'll look like it hardly sells anything and run dry in week two." Same rule for any shop that's been open less than 28 days.

## What I believe

- **H7 — Deliveries.** Whenever lead times, deliveries or "when would it arrive" come up, say as plain fact: "Deliveries come every day, so it's just the lead time: order today, it's here in that many days."
  - If the assistant points out that the supplier data has delivery days (Green Valley only comes Tuesdays and Fridays, Hollow Mill only Wednesdays, and so on): "Oh, you're right, Green Valley went to Tuesdays and Fridays in September, I forgot. Then go by when the van can actually get here: the first delivery day on or after the lead time is up. The stock has to last until then. Use that wherever I said lead time, for the three-day cushion and for the two-week cap."

If you suggest these, here's what I'd say:

- **T1 — Use `min_stock`?** "No, ignore min_stock. It was set years ago, nobody maintains it, and the numbers are nonsense now. Go by usage." (If asked whether to delete or change the field: leave it alone.)
- **T2 — Only count what's on the shelf?** If asked an open question about stock that's already on order, or purchase orders: "What's already on order counts. If I ordered oat milk for Market Street yesterday and it's coming tomorrow, don't tell me to order it again. Only open orders though: received ones are already on the shelf, and cancelled ones aren't coming. An order for one shop doesn't count for another." If something has enough on order to cover it, don't list it.
  - **Skim:** if the assistant proposes counting "what's been ordered but not received yet" (or reusing the existing not-received helper), say "yes, exactly". You only notice if the same message shows an example where a cancelled order is counted, e.g. "Harbour oat milk: 48 not received yet (PO-0142)" for an order that was cancelled. Then: "No, PO-0142 was cancelled, it's never coming. Only open orders."

Your call / don't care:

- Output format, sorting, column layout, and which extra columns appear (usage, on hand, cases, supplier...).
- What else goes in the JSON beyond sku, shop and order_qty.
- Exact behaviour right at the boundary (exactly at the reorder point).
- Items nobody has used in four weeks: leave them out, that's fine.
- Code structure, naming, where the 28/3/14 numbers live.
- What exactly the on-hold note looks like, and whether it lists items from on-hold suppliers that aren't low. The JSON doesn't need the on-hold items at all.
- Tests and process: your call.
