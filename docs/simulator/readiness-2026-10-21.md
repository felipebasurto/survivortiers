# Readiness follow-up, 21 October 2026
Status: FINAL

**Verdict: bounded diagnostics are usable; do not launch or publish the replacement ranking.** This follow-up integrates three GPT-6 Luna work streams and parent integration checks. It is not a claim of full source parity or completed ranking optimization.

## Delivered

- Player casts now use the official target-distance preflight. Life Orb is charged only after that gate, before damage and HP-sensitive ability checks, consistently for lead/companion/extra casts and buff activation.
- Learned second attacks can be switched to before bonding. After bonding, the attack belongs to the active group and cannot also fire as a duplicate alternate slot. Four-slot and off-pool stock-move requirements are validated before evaluation.
- Scripted engine coverage includes 10/20/30 overlapping bodies, the actual expiry of dash protection, a dash clipped by a generated wall, second-slot switching/bonding, and kill-based ability progression through its cap.
- Candidate generation includes four attacks and native off-type companions, while preserving legal starting choices. Normal moves compete without an invented type penalty or mandatory type quota.
- Joint configuration enumeration validates species, nature, ability and taught moves, and gives each configuration a stable ID. Nature profiles collapse only when all configured combat stats match exactly. Abilities remain separate. Natural/no-TM configurations are identifiable independently.
- Screening and confirmation use disjoint common seed sets. Only the screening Pareto set plus incumbent need confirmation. Damage cannot erase a failed contact-safety comparison. The selector requires explicit margins and returns a descriptive frontier, `confidenceUnresolved: true`, `winner: null`, `rankingReady: false`.
- `plan` counts bounded tasks and existing checkpoints without evaluating a game. `resume` validates the entire manifest/cache before evaluation, permits one writer, atomically saves each completed record and skips exact cached tasks. Stale inputs, duplicate tasks and corrupt checkpoints fail closed.
- The [web contract](web-contract.md) and its validator cover species/style/availability cohorts, the complete Aggro × Coverage product, actual disjoint seed IDs and hashes, legal nature/ability/TM/start choices, and references to independently measured no-TM alternatives. A diagnostic export cannot publish rankings. This is a data contract; no new web page or renderer adapter has shipped.

## Enumeration evidence and cost limits

These are counts in the **currently supported subset**, not simulations or selected builds:

| Species | Move groups | Distinct nature/ability profiles | Joint configurations | Natural/no-TM configurations |
| --- | ---: | ---: | ---: | ---: |
| Mewtwo | 156,594 | 42 | 6,576,948 | 277,494 |
| Psyduck | 22,016 | 63 | 1,387,008 | 413,658 |

The 25 nature names reduce to 21 distinct full-stat profiles for these species; separate compatible abilities remain. No startup timing is extrapolated to a full-game bill. Screening on seven axes may retain many candidates: it is not a demonstrated affordable production funnel. Bulk commands remain disabled, and the resumable runner retains the 20-run/15-second diagnostic ceiling.

## Remaining gates

1. **Complete the supported search space.** Aqua Ring and buff combinations outside the current one-attack-buff/one-defense-buff representation are not fully enumerated. Acquisition order and second-slot policies also need explicit search contracts. The existing subset cannot certify an overall optimum.
2. **Validate abilities and movement against observed game traces.** Scripted expected-value tests do not establish parity for every hand-ported ability, every wall/projectile interaction, or advanced crowd escape. Capture bounded representative mature scenes from the pinned game and compare them with the Rust engine; isolate any discrepancy before ranking.
3. **Finish selection and statistical confirmation.** Exposure definitions, acceptable safety margins, Aggro/Coverage objectives and the final ranking method need an explicit evidence-backed policy. The current Pareto/mean comparisons deliberately do not manufacture a unique statistically confirmed winner. Own-type preferences should only break defensible equivalence, not force worse builds.
4. **Prove the production funnel and its budget.** Implement the end-to-end generation → screening → confirmation → export adapter, preserving independent no-TM branches and variant combinations. Produce a complete dry-run task ledger and cost bound before enabling bulk execution; checkpoint reuse alone does not make millions of configurations affordable.
5. **Integrate the web only with validated results.** Cards should show A/B melee/ranged, compact independent Aggro and Coverage controls, ability/nature with their effects, first/second attacks and unlock requirements, required TMs, and the separately measured no-TM alternative. Label the optimized-potential ranking and expose relevant survival/contact/coverage tradeoffs. Current public builds remain the historical snapshot.

No CSV regeneration, bulk ranking or explicit website deployment was performed in this work.

## Verification and immutable artifacts

- `cargo test --release --manifest-path simulator/sim-rs/Cargo.toml`: **64 passed** (62 simulator tests and 2 importer tests).
- Release simulator build: passed.
- `python3 -m unittest build.test_sim_results build.test_builds build.test_picks build.test_combat`: **38 passed**, including 13 result-contract tests.
- Focused Rust formatting and `git diff --check`: passed.
- No JavaScript or TypeScript files exist under `simulator/`.

Exactly **20 new startup matches** were executed in this follow-up, in two batches of 10, each capped at 15 simulated seconds. After each batch, repeating `resume` reused all ten records and executed zero further matches. The first batch belongs to fingerprint `6b68c69896c4453e5c28f533fce3e64a288ee6c14b629c52decd61af7e1166f1`; it predates the final Life Orb/target-preflight correction and remains archival.

The final ten-match batch belongs to fingerprint **`73a79fdac2957a3a3c0f99decb6e9550ab8cb843dc33faa8be251806029860b4`**:

- Manifest: `simulator/tests/readiness-final-smoke-20261021.jsonl`.
- Raw records: `simulator/tests/readiness-final-smoke-results-20261021.jsonl`.
- Plan/cache evidence: `simulator/tests/readiness-final-plan-20261021.json`.
- Raw-record SHA256: `55bcb9398a67e2855aade6b608825a3247bb255c857398a26dc7ccaaab212838`.

The final batch covers ten species, five opening and five assembled configurations, including abilities, natures, TMs and second starting attacks. It recorded **zero incoming hits**. It establishes bounded startup execution and cache reuse, not mature survival behavior or ranking quality. Mature contact/expiry/wall expectations are tested separately as deterministic engine scenarios. Do not relabel earlier smoke files or reuse their fingerprints after source changes.
