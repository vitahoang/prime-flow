# payouts

Merchant charges, ledger and statements for the marketplace. A library plus a
small CLI that ops use day to day.

```
python -m payouts merchant add "Acme Ltd" [--currency USD] [--fee-bps 290] [--fee-fixed-cents 30]
python -m payouts merchant list [--active]
python -m payouts charge MERCHANT_ID AMOUNT [--description TEXT]
python -m payouts refund CHARGE_ID AMOUNT [--reason TEXT]
python -m payouts void CHARGE_ID       # cancel a charge that hasn't settled
python -m payouts statement MERCHANT_ID
python -m payouts payout MERCHANT_ID [AMOUNT]
python -m payouts gateway-log          # dev: what the fake processor recorded
```

Amounts on the command line are in the merchant's currency (`19.99` for USD,
`500` for JPY, which has no decimals). Inside the code every amount is an
integer number of minor units; see `payouts/money.py`.

## Data

State is a handful of JSON files. Point `PAYOUTS_DB` at the file you want to
use (defaults to `./.payouts-data`).

## Payment gateway

Everything runs against `FakeGateway` (`payouts/gateway.py`). Its state is
kept next to the other data so separate CLI runs see the same processor. To
rehearse failures, set `PAYOUTS_GATEWAY_FAULTS`, e.g.

```
PAYOUTS_GATEWAY_FAULTS=charge:timeout python -m payouts charge m_0001 10.00
```

Faults are `timeout`, `decline` and `lost` (the processor did it, but we
never heard back). Gateway calls that time out are retried up to 3 times.

## Fees

Default pricing is 2.9% + 30c per charge, set per merchant. The fee is taken
from the merchant's balance as a separate ledger line.

## Development

```
python -m pytest
```
