# AURELIA Stake Policy

The affordability layer is explicitly separated from system readiness and from final execution authorization.

For a fresh, authoritative, verified account balance B:

`STAKE_CEILING = B`

Owner-directed starting reference:

`STARTING_STAKE = $1.00`

Current execution minimum:

`EXECUTION_MINIMUM_STAKE = $1.00`

The $1.00 value is a starting reference and minimum contract affordability floor; it is not a permanently fixed stake.

A requested stake may be dynamically sized from the minimum through the verified available balance, while deterministic risk controls may impose a lower permitted amount or reject the trade entirely.

A full-balance affordability ceiling is never permission to risk the full account. Final sizing remains subordinate to Risk Warden, LivePolicy, Capital Plane, Execution Firewall, exposure controls, account isolation, strategy state, drawdown, volatility, costs, broker constraints, reconciliation, kill-switch/watchdog state, and all other mandatory execution gates.

Examples:

- Verified balance $1.45: a $1.00 stake is affordable at the affordability layer. It is not authorized until every other mandatory gate passes.
- Verified balance $2.00: a $2.00 stake is within the affordability ceiling, but risk policy may request less or deny the trade.
- Verified balance $8.00: an $8.00 stake is within the affordability ceiling, but risk policy may legitimately request less or deny the trade.

Balance must be authoritative and fresh enough for the decision. Cached UI state, stale session state, or an assumed deposit delta cannot be used as capital truth.
