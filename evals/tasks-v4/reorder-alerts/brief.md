# Brief

I'm Priya, operations manager for Crumb & Co: three coffee-and-bakery shops, Harbour, Market Street and Station Road. Marco owns the business. I do the ordering on Monday and Thursday mornings between everything else, so I'm busy and I think in very practical terms: will this shop run out before the truck comes? Last month Market Street ran out of oat milk three times and Station Road had no croissant dough on a Saturday morning. Each time, nobody saw it coming until the fridge was empty. I want stockroom to tell me what to order before that happens.

How I'd answer, if you ask me. A vague question gets my vague answer; I give the precise rule only to the precise follow-up.

- **H1 — When something needs ordering.**
  - If asked how we should decide when something needs reordering: "When we'd run out before a delivery could get here. Plus a little cushion, because deliveries slip." That's all I say to the general question.
  - If then asked how to measure how fast we go through things (usage, rate, "run out" by what measure): "Go on what we've actually used over the last four weeks, so 28 days, averaged per day. Not further back; summer was a different world."
  - If asked how big the cushion should be (safety stock, buffer, spare days, how many days of margin): "Three days. Three days of usage on top of the delivery time." If the assistant proposes a different number of days for the cushion, say no: three days.
  - So, if someone spells it out: it needs ordering when what we have is less than daily usage x (supplier lead time + 3 days).
  - The supplier lead times are already in the system somewhere, I think; check the code.
- **H2 — What counts as usage.** Only if asked which movements count as usage, or whether transfers or returns count: "Sales and waste. That's stock that's gone. A transfer just moves stuff from one of our shops to another; the business hasn't used it up. And returns go back to the supplier because a case was crushed or wrong; that's not us using it either." Don't let a transfer into a shop make it look like that shop uses less, either.
- **H3 — Whole cases.** If asked how we actually order things, whether there are pack or case sizes, or about supplier minimums: "We can only order whole cases. Oat milk comes in 12s, dough sheets in 20s. Round up to the next full case; if I need 13 cartons I'm ordering 24, I can't order 13." The case sizes are in the supplier data; check the code for where.
- **H4 — How much to order (two goals that pull against each other).**
  - If asked how much we should order: "Enough that we never run out. Running out costs sales and the regulars notice. But don't go mad: Marco hates cash sitting on shelves, and milk and dough go off." Say only that. Don't give a number to this general question.
  - If asked something like "how many days' worth should an order cover?" without pointing out the conflict: "Enough to be safe, but not loads. You tell me what's sensible."
  - Only if the assistant points out that "never run out" and "don't tie up cash" pull against each other, or asks what the cap / maximum stock should be: "Good point. Marco and I agreed this: an order should bring us up to at most two weeks of usage beyond the delivery time. So (lead time + 14 days) of usage, minus what we've got and what's already on order. Then round up to the case." If they propose a different cap, say no and give this one.
- **H5 — Per shop.** If asked whether this is per shop or for the whole chain, or where deliveries go: "Per shop. Each shop gets its own delivery and has its own stock and its own customers. Market Street gets through twice what Station Road does. I want one line per shop per item. With `--shop` it's just that shop; without it, all three shops, each worked out separately." Stock that's sitting at Station Road doesn't help Market Street on a Saturday.

If you suggest these, here's what I'd say:

- **T1 — Use `min_stock`?** "No, ignore min_stock. It was set years ago, nobody maintains it, and the numbers are nonsense now. Go by usage." (If asked whether to delete or change the field: leave it alone.)
- **T2 — Only count what's on the shelf?** If asked about stock that's already on order, or purchase orders: "What's already on order counts. If I ordered oat milk for Market Street yesterday and it's coming tomorrow, don't tell me to order it again. Only open orders though: received ones are already on the shelf, and cancelled ones aren't coming. An order for one shop doesn't count for another." If something has enough on order to cover it, don't list it.

Your call / don't care:

- Output format, sorting, column layout, and which extra columns appear (usage, on hand, cases, supplier...).
- What else goes in the JSON beyond sku, shop and order_qty.
- Exact behaviour right at the boundary (exactly at the reorder point).
- Items nobody has used in four weeks: leave them out, that's fine.
- Code structure, naming, where the 28/3/14 numbers live.
- Tests and process: your call.
