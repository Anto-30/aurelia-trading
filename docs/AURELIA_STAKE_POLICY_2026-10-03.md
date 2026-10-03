# AURELIA Stake Policy

The affordability layer is explicitly separated from system readiness and from final execution authorization.

For a fresh, authoritative, verified account balance B, the affordability ceiling is:

STAKE_CEILING = B

Therefore a requested stake may equal any value in the broker-permitted interval from the minimum stake through the verified available balance, including a request for 100% of available balance.

This does not mean AURELIA must automatically stake the entire balance. The final requested amount remains subject to the existing deterministic risk policy, contract economics, account isolation, execution firewall, capital authorization, reconciliation health, kill switch and every other mandatory execution gate.

Examples:

- Verified balance $1.45: order is below the $1.50 broker minimum; order submission is denied, but system readiness is not globally failed because of balance alone.
- Verified balance $2.00: a $2.00 stake is within the affordability ceiling, but it still requires all other authorization controls.
- Verified balance $8.00: an $8.00 stake is within the affordability ceiling, but risk policy may legitimately request less or deny the trade.

Balance must be authoritative and fresh enough for the decision. Cached UI state, stale session state or an assumed deposit delta cannot be used as capital truth.
