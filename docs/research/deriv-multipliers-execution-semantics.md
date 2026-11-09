# Deriv Multipliers execution semantics — release gate

## Product distinction

Do not treat Deriv Multipliers as MT5 CFDs or as ordinary spread-only positions.

- MT5 CFDs express stop-loss and take-profit as underlying price levels and use symbol-specific volume, tick-value, margin and spread specifications.
- Deriv Multipliers are broker-priced contracts. The API's `limit_order.stop_loss` and `limit_order.take_profit` values are monetary contract-value thresholds. The proposal response may return mapped pip/price barrier values, but those are broker-derived outputs.
- The API catalogue listing `MULTUP` / `MULTDOWN` is not proof that a proposal for the selected symbol and account is valid.
- Deriv's trading terms describe commissions and cancellation fees for Multipliers. Do not model this product as universally commission-free or use an MT5 CFD spread model.

## Required price-level mapping

The AURELIA 369/MSNR strategy is expressed in underlying price coordinates: entry, ATR-based stop, and opposing 369 target. That strategy is **not certified as directly mapped** to Multipliers by merely setting monetary stop-loss/take-profit values.

A mapping may be considered only after all of these checks are evidenced:

1. Obtain broker proposal quotes for the exact symbol, direction, currency, stake and multiplier.
2. Obtain the broker's minimum/maximum stake and stop-loss/take-profit validation bounds.
3. Convert the strategy's underlying price stop/target to candidate monetary P&L thresholds using the broker's contract economics.
4. Submit those values as proposal `limit_order` fields only; do not buy.
5. Read the broker-returned mapped stop/target barrier values and compare them to the strategy's intended price levels within the instrument's verified tick size.
6. Repeat for both directions, relevant multiplier choices, stake sizes and volatility regimes.
7. Reconcile commissions, minimum fees, cancellation fees, slippage and stop-out behavior.
8. Keep `strategy_stop_mapping_verified=false` until all mappings pass and the evidence is tied to the exact source commit.

A proposal quote is not a broker-side lifecycle test. A broker-side lifecycle test requires a separately approved Demo-only order workflow; it is not run by the public proposal verifier.

## Current evidence status

A prior public probe recorded that R_100 was active and that its contract catalogue listed `MULTUP` and `MULTDOWN`; that same probe recorded `ContractBuyValidationError` for both proposal requests. These are historical observations, not a new verification in this branch. This public-only branch deliberately does not repeat proposal requests, and it does not run any account-authenticated proposal checker. Therefore the R_100 Multipliers product path remains unqualified despite catalogue presence.

`1HZ100V` is a separate symbol from `R_100`. A catalogue or proposal result for one symbol cannot be transferred to the other, and it cannot transfer historical strategy results or instrument specifications.

## Permanent restrictions

- No `buy`, `sell`, or order-modification request in public verification.
- No agent, model or research process may grant capital authority.
- Missing quote, account identity, minimum stake, commission, mapped stop/target, or feed-equivalence evidence means BLOCKED.
- CI success, a catalogue listing, or a one-hour transport soak does not authorize live execution.

Official references:
- [Deriv Multipliers API workflow](https://developers.deriv.com/docs/workflows/)
- [Deriv trading terms](https://deriv.com/terms-and-conditions/trading-terms)
- [Deriv MT5 historical export instructions](https://community.deriv.com/t/deriv-mt5-historical-data/29430)
