# Repository Intake — Upstream Revision Pins (2026-10-13)

GitHub commits API lookup captured these default-branch tip SHAs on 2026-10-13 UTC. They are immutable revisions observed at lookup time, not an assertion that the projects are secure or suitable for production. Recheck before use.

| Repository | Observed upstream tip SHA | Last commit subject |
|---|---|---|
| https://github.com/pasky/chrome-cdp-skill | `ffea76a24b0471663ddd9d9f24335bbc442b6266` | v1.1.0 |
| https://github.com/anthropics/claude-quickstarts | `9ec32b91df50b0d4906cae64b13c6298055ff40d` | Cj ant/computer browser toolsets (#508) |
| https://github.com/siteboon/claudecodeui | `7c3049fe8e157f12b7add3e496d8d2fe6fa5c014` | chore(release): v1.37.4 |
| https://github.com/ChrisWiles/claude-code-showcase | `a95518f0cb67e86230119da40429169bc4c35a6f` | feat: add MCP servers, LSP support, and /ticket command |
| https://github.com/decebals/claude-code-java | `0d98fe9bd62923e819568ee1e041a1bf320f74d4` | docs: put Fixed after Changed, as in 1.0.0 |
| https://github.com/d-kimuson/claude-code-viewer | `9367cf006be9965c954e6cd36526f2195dce67ea` | chore: release v0.8.2 |
| https://github.com/intel/auto-round | `4663212ac4fd18be2b4ec4fa7c79c6e2e6fa9ce1` | Don't rewrite packed modules as float weights when resuming (#2386) |
| https://github.com/D4Vinci/Scrapling | `7a684934907a8c7feaafe9ff1ccfd9d45cc26faf` | docs: update a sponsor info |
| https://github.com/cyberchitta/scrapling-fetch-mcp | `8ed4c0df0979ca758e6e13ae84e6cdbe129e1a7a` | chore: gitignore _notes working-notes symlink |
| https://github.com/popiliadam/platinum-seo-engine | `ffdf24da84cd5d52f755f156707d9bd14f7c0135` | Merge branch 'fix/secret-scan-boundary' |

## Evidence limits

These revisions were resolved via GitHub's commits API. README files were fetched for all ten repositories. The intake remains a documentation and research review: source trees were not cloned/executed, actual license files and full dependency trees have not all been inspected, and no local vulnerability scan, regression test, installation or runtime integration has been performed.

## Adoption status

- **BLOCK:** siteboon/claudecodeui pending version-specific security advisory verification and regression evidence.
- **HOLD:** chrome-cdp-skill; d-kimuson/claude-code-viewer; Scrapling and scrapling-fetch-mcp pending isolation, authentication and network-security review.
- **REFERENCE ONLY:** anthropics/claude-quickstarts and ChrisWiles/claude-code-showcase; select components, do not wholesale-import demos/hooks/workflows.
- **CONDITIONAL:** decebals/claude-code-java only if Java is actually used.
- **RESEARCH ONLY:** intel/auto-round; require reproducible model quality and performance benchmarks.
- **OUTSIDE TRADING RUNTIME:** popiliadam/platinum-seo-engine; separate marketing workspace only after license and permissions review.

AURELIA invariants remain unchanged: one canonical system, one capital plane, one release authority, one evidence lineage. External agents, browser tools and scraped content cannot authorize secrets, code changes, risk overrides, broker operations or orders.
