# External AI and ML Tooling Sync — 2026-10-05

Four additional public sources were added to the AURELIA external federation registry, bringing the registry from 78 to 82 unique sources.

| Source | AURELIA role |
|---|---|
| AEON-7/Ornith-1.0-35B-AEON-Ultimate-Uncensored | SANDBOX_ONLY |
| OrnitheMC/ornithe-standard-libraries | REFERENCE_ONLY |
| ornith-ai/Ornith-1 | SANDBOX_ONLY |
| ARahim3/mlx-dspark | TOOLCHAIN_ONLY |

The Ornith model sources are treated as untrusted model/tooling inputs rather than trading engines. They may be evaluated for agent reasoning, research orchestration, coding assistance, or isolated experiments. They cannot authorize trades or bypass deterministic AURELIA controls.

The MLX-DSPark source is treated as inference/toolchain infrastructure. Its purpose is acceleration of supported local model inference, not trading execution.

No source in this federation receives capital authority, broker transaction-write authority, secret-reading authority, production deployment authority, or LIVE_LOCK mutation authority.

Repository membership does not constitute model validation, security approval, strategy qualification, profitability evidence, broker compatibility, or live-trading authorization.

The existing AURELIA research/capital-plane boundary remains authoritative.
