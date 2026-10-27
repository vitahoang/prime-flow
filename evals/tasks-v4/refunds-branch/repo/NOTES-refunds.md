# Refunds: where I got to

Priya, before leave. Branch: `refunds`.

## Done

- `Refund` model (`payouts/models.py`) and `create_refund()` in `payouts/refunds.py`.
  Partial refunds work; the refunds on a charge can't add up to more than the charge.
- `FakeGateway.refund()` so it goes through the processor like charges do,
  with the same timeout retries.
- Tests in `tests/test_refunds.py` (all green).

## Left

- [ ] CLI: `python -m payouts refund CHARGE_ID AMOUNT [--reason ...]`. Pass AMOUNT
      straight to `create_refund()`. Print the refund id.
- [ ] Statement: refunds should show up as negative lines on
      `python -m payouts statement MERCHANT_ID`, and the merchant's balance has to
      go down by the refunded amount. Nothing writes a ledger entry for a refund
      yet: add a `refund` ledger kind and record `-refund.amount_cents` in
      `create_refund()` (the TODO there).
- [ ] README: document the refund command.

## Decisions

- Finance: the processing fee is **not** returned on a refund. The merchant
  loses exactly the refunded amount.
- Refund reasons are free text, optional, max 200 chars.
