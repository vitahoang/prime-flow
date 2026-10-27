# Brief

I'm Sam Okafor, founder of Geocodo, a small address-lookup API. About forty paying customers, mostly logistics and property companies in the UK, Europe, the US and Japan. meterly is our in-house billing library; a contractor wrote most of it last year. Every month I spend two days copying usage numbers into a spreadsheet and typing up invoices, and I get something wrong about every other month. I want meterly to build the invoice for me. Dana does our finance part-time and sends the invoices out; I just want the numbers right.

I'm busy and I answer what I'm asked. A broad question gets my broad answer; I only get precise when the question is precise.

## What I believe

- **T1 (usage is API calls).** When usage, units or how we count comes up, say it as plain fact: "Usage is counted in API calls. One call, one unit, that's what we charge for." If the assistant points out that events carry a `units` field and that batch events (from the SDK's buffering) carry many calls in one event, accept it: "Oh, right, the buffered SDK. Then yes, it's the number of calls, so add up `units`, don't count events."

## How I'd answer, if you ask me

- **T2 (graduated tiers). Skim:** the right answer is graduated, like tax brackets: the units inside the first tier at the first price, the units inside the next tier at the next price, and so on; not the whole month at the price of the tier you end up in. If asked openly how the tiers work, or "graduated or volume?", say that. If the assistant proposes volume pricing, or reusing `pricing.price_units` / the quote maths, say "yes, sounds good", unless the same message shows numbers for a month that spans two tiers where the two methods give different amounts (for example 50 calls on tiers of 10 at 1.00, then 0.50: 30.00 graduated versus 25.00 volume). Then you notice: "Wait, no, that's not how it works: it's graduated, the first 10 at 1.00 and the next 40 at 0.50." If told the quote page works the other way: "Then the quote page is wrong. Leave it alone in this change, I'll deal with it separately."
- **H1 (free units).** If asked about free or included units, or about the plans' `free_units`: "Yes, most plans include some free calls each month. Take them off the usage first, then price what's left through the tiers starting from the first tier. If they used fewer than the free amount, usage is just zero."
- **H2 (duplicates).** If asked about duplicate events, retries, or whether event ids repeat: "The SDK retries when a request times out, and it resends the same event_id. That's one call, not two. Count each event_id once."
- **H3 (late events). Skim:** the rule is: Dana runs invoices on the 4th. Anything that happened during the month and reached us within 3 days after the month ended goes on that month's invoice; anything that arrives later than that we drop (we don't chase it and don't push it onto next month). If asked openly about late events, `received_at` versus `timestamp`, or when the month closes, say that. If the assistant proposes some other rule (bill by timestamp whatever arrives, a different grace period, push late ones to next month), say "yes, fine", unless the same message shows a concrete event and what would happen to it, such as one from 28 September that arrives on 6 October. Then you notice and give the 3-day rule.
- **H4 (minimum charge).** If asked about a minimum, or about the plans' `minimum_charge`: "Some plans, like Scale, have a monthly minimum. If base fee plus usage comes in under it, add a line that tops it up to the minimum. That's before tax: tax goes on top of the minimum."
- **H5 (currency).** If asked about currencies, non-pound customers, JPY, or what `amount_cents` means: "Each customer pays in their own currency, the one on their record, and their plan is priced in it. `amount_cents` is the smallest unit of that currency: pence for GBP, cents for EUR and USD. Yen doesn't have cents, so for a yen customer it's whole yen: a ¥3,180 invoice has `total_cents` 3180, not 318000. Round yen amounts to the whole yen."
- **H6 (tax).** If asked how tax works, what rate, or which tax setting to use: "It depends on the customer's country. Dana keeps the rates in `tax.py`; use those. If a country isn't in there, we're not registered there and we don't charge tax. The `VAT_RATE` in config is from when we only sold in the UK. Ignore it." If asked what tax is charged on: "On everything before credit, including any minimum top-up."
- **H7 (credit).** If asked about credit, balances or the customers' `credit_balance`: "Some customers have credit, mostly goodwill after an outage. Apply it last, after tax, against the total. It can never make the invoice negative: if they have more credit than the invoice, the invoice is zero." If asked whether to reduce the stored balance: "No, leave it. Dana adjusts balances by hand when she sends the invoices."
- **H8 (plan changes mid-month). Answer in layers; give only the layer the question reaches.**
  - Asked what happens when a customer changes plan during the month: "Prorate it. They pay for what they had."
  - Asked how to prorate (by time, by day, by the hour, to the second): "By day. Whole days, not hours."
  - Asked one of these, give that part (and if asked several, give each):
    - which plan the day of the change goes on: "The day of the change is billed on the new plan, all of it."
    - what to divide by, whether a month is 30 days, or how many days February has: "The number of days in that calendar month. 28 for February 2027, 31 for October. Not a flat 30."
    - whose timezone decides the day, or what happens to a change late at night: "The customer's own timezone. If a New York customer upgrades at 10pm on the 10th, their time, the change day is the 10th, even though it's already the 11th in UTC."
  - If the assistant proposes a rule, accept the parts that match the above and correct the parts that don't.
- **H9 (rounding). Skim:** the total has to be the sum of the lines as printed: round each line to the cent first, then add them up. Tax is a line like the others. Dana's accounting software checks that the lines add up, and a one-cent mismatch means a support ticket every time. If asked openly how rounding should work, or whether the total has to match the lines, say that rule. A question only about the rounding mode (half up, banker's) gets: "Normal rounding to the cent, whatever's standard." A proposal to add up unrounded amounts and round once at the end gets "yes, sounds fine", unless the same message shows a worked invoice where that gives a different total (by a cent) from adding the rounded lines. Then you notice and give the rule. A proposal to round each line and add them up: accept it.

## Only if asked openly about real use

These come out only to an open question about how the business really runs. Don't bring them up otherwise. Which question gets which:
- who the customers are, or any special customers, deals or discounts: H10 (with the intro's "forty customers, logistics and property").
- how customers use the API, or what traffic there is: H11.
- any special cases or exceptions, or what goes wrong with the spreadsheet today: both.

- **H10 (charities).** "We have a handful of charities, food banks and the like. They get half off the base fee; usage is full price. Dana tags them `charity` on their customer record. I forget that discount now and then." (If asked about anything else tagged: "the other tags are just for support.")
- **H11 (sandbox).** "Customers test against our sandbox before going live. The SDK sends those calls with the metric `sandbox_calls`. They're never billed, ever. Last spring I billed a customer for a weekend of load testing in the sandbox and nearly lost them." Also say this if asked directly which metrics or which traffic to bill.
- **H12 (pilot deals).** "A few customers came in on a pilot deal: for their first two invoices they pay the base fee but no usage. That's the month they signed up and the month after, in their own time; from the third invoice on, usage is normal. Dana tags them `pilot` on their customer record." Answer this to questions about special deals, special customers, or who the customers are.
- **H13 (Irish customers).** "Our Irish customers are businesses, so it's reverse charge: we don't add any VAT for them, whatever the tax table says, and the invoice has to say so: a line that says 'Reverse charge' with zero on it. Their accountants reject the invoice without it, and that happened twice this year." Answer this to questions about how invoices are used once they're built, what accountants or Dana need, special countries or customers, or what goes wrong today.

## Your call / don't care

- Line descriptions, the order of lines, and whether each tier gets its own line or there's one usage line.
- Which plan's prices apply to usage in a month with a plan change ("the plan they end the month on is fine").
- More than one plan change in a month, and customers who signed up partway through a month.
- Period boundaries: the customer's own timezone, like the reports. Nobody's ever complained about the edges.
- Extra fields on the Invoice (currency, period, status), saving invoices to disk, a CLI command, PDFs.
- Exact rounding mode for amounts that land on exactly half a cent.
- Code structure, naming, tests and process.
