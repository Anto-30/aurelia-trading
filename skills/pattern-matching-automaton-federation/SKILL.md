# Pattern Matching and Automaton Federation

## pyahocorasick
Pinned source: WojciechMula/pyahocorasick @ 4e28d29898f1019d9706485b2a06026466814d9d.
AURELIA may use the library for deterministic, non-capital pattern matching such as news/entity lexicons, event classification, and high-volume text scanning. The pinned Python package is installed as a normal runtime dependency; it has no broker, capital, secret, or policy authority.

## Conway Automaton
Pinned source: Conway-Research/automaton @ d8f816881fd24b6f5e3d616e59edec387a447667.
Use as architecture/threat-model reference only. Do NOT install its autonomous runtime into the AURELIA production process. Its documented design includes its own wallet, financial operations, self-modification, replication, and autonomous survival mechanisms; these are incompatible with AURELIA's deterministic capital-plane model. GrokBot and ClaudeCode may inspect it in an isolated sandbox.

## Assignment
- GrokBot: research, architecture comparison, fast pattern-matching design, adversarial review.
- ClaudeCode/Dev: implementation, dependency maintenance, tests, sandbox inspection.
- AURELIA: pyahocorasick as a deterministic library dependency; Conway Automaton as reference only.

## Hard boundary
Neither source can authorize capital, submit broker orders, read production secrets, mutate LIVE_LOCK/FINAL_EXECUTION_AUTHORIZATION, bypass Risk Warden/Execution Firewall, or create a second trading engine.
