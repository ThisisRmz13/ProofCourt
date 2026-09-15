# ProofCourt

**A decentralized arbitration court for escrows with natural-language conditions — built on GenLayer.**

ProofCourt locks funds against a condition written in plain language ("PR #42 is merged", "the service had 99% uptime", "the delivery arrived before Friday"), lets the beneficiary claim completion, and has a jury of AI validators **independently investigate the claim** before releasing or refunding the money. No trusted middleman. No "trust me, the work is done".

## The problem

Escrow and bounty systems today face a wall:

- **Smart contracts can't read the world.** `if (prMerged == true)` requires an oracle for every single condition type.
- **Manual review doesn't scale and isn't trustless.** Traditional bounty platforms (Gitcoin, Algora) depend on the honesty of the payer or the platform.
- **One LLM call is not arbitration.** A single model reading a claim can be fooled by a link the claimant hosted themselves, a transaction with the wrong recipient, or evidence taken out of context.

ProofCourt treats dispute resolution as what it is: **litigation** — with a leader, an adversarial jury, standards of proof, and an appeals process.

## How it works

```
payer ──create_escrow(condition, beneficiary)──▶ funds locked
beneficiary ──submit_claim(text, links)────────▶ status: CLAIMED
anyone ──resolve()─────────────────────────────▶ AI jury investigates
                                                   │
                     ┌─────────────────────────────┼──────────────────────┐
                     ▼                             ▼                      ▼
                 RELEASE                        PARTIAL                 REFUND
              funds → beneficiary        status: appealable        funds → payer
                     │                             │
                     └────────── any party ──appeal()──▶ condition is rewritten
                                                         into strict atomic checks,
                                                         then resolve() runs again
```

### The three AI roles

| Role | Job | Mechanism |
|---|---|---|
| **Leader** | Produces a verdict (RELEASE / REFUND / PARTIAL) with confidence + evidence it personally verified | `gl.nondet.exec_prompt` with the Leader prompt |
| **Compare jury** | Re-derives the verdict **independently** — refetches the same evidence, ignores the leader's summary — and rejects the leader if outcomes disagree | Custom validator in `gl.vm.run_nondet_unsafe` using the Compare prompt |
| **Appeal judge** | Rewrites a failed condition into strict, atomic, binary checks resolvable from on-chain/API data | `gl.eq_principle.prompt_non_comparative` |

### Design decisions that matter

1. **The claim is never evidence.** Beneficiary-supplied links are fetched and passed to the model explicitly labeled *UNTRUSTED*. The prompts enforce independent verification: block-explorer traces, event logs, timestamps, amounts, recipients, token addresses, direction.
2. **Anti-deception checklist baked into the prompt:** wrong amount / wrong recipient / wrong token / wrong direction / evidence out of order / correct transaction outside the time window / claimant-hosted data.
3. **Confidence thresholds live in code, not prose.** Escrows above a value threshold require confidence ≥ 0.9 with direct on-chain proof; a low-confidence RELEASE is automatically downgraded to PARTIAL (appealable), never guessed.
4. **PARTIAL is a first-class outcome.** "Cannot verify" is never treated as "false": a leader may REFUND only on **affirmative contradiction** (wrong amount, wrong recipient, verifiably absent event). Anything it cannot verify from available data is PARTIAL — appealable, never guessed.
5. **Every verdict is on-chain.** All verdicts, confidence scores, evidence summaries and reasoning are stored in `verdict_log` — anyone can audit *why* the money moved.

## Why this is not "just an Intelligent Oracle"

| | Typical Intelligent Oracle (e.g. weather check) | ProofCourt |
|---|---|---|
| Nature of question | Cooperative fact: "did it rain?" | **Adversarial dispute:** two parties bet on a fuzzy condition |
| Consensus pattern | `prompt_non_comparative` — validators check the leader's answer against criteria | Custom leader/**jury** pattern — validators re-derive the verdict from independently fetched evidence |
| Trust model | One leader + criteria check | Adversarial: leader is assumed untrusted until the jury independently agrees |
| Ambiguity handling | Force a binary answer | **PARTIAL state + appeal loop** that sharpens the condition until it is binary |
| Fraud resistance | N/A | Explicit deception-pattern checklist; claim data treated as untrusted |
| Money movement | Fixed payout rule | Conditional release/refund governed by thresholds in code |

The oracle pattern answers questions. ProofCourt **settles disputes** — a different problem, requiring investigation, standards of proof, and appeals.

## Example: auto-bounty

1. Alice creates an escrow: *"1,000 tokens if PR #42 by @bob is merged into `main` before 2026-10-01"*
2. Bob merges the PR and calls `submit_claim("Merged, see commit abc...", ["https://github.com/.../pull/42"])`
3. `resolve()` — validators fetch the GitHub API and the chain themselves, cross-check author, merge commit, timestamp, and target branch
4. Verdict RELEASE → funds move to Bob automatically. Alice never had to click "approve", Bob never had to trust her.

The same flow works for freelance milestones, SLA credits, agent-to-agent commerce (x402/ACP payments), and insurance-style payouts.

## Run it

### On GenLayer Studio

1. Open Studio → paste `contract.py` → **Deploy new instance** (consensus runs the deploy — wait for FINALIZED)
2. `create_escrow(condition, beneficiary, deadline)` — it's **payable**: enter the escrow amount in the **Value** field (e.g. `100`). The funds are locked from the payer's wallet, not held by a trusted platform.
3. `submit_claim(escrow_id, claim_text, claim_links)` — beneficiary files the claim
4. `resolve(escrow_id)` — the jury runs: the leader fetches evidence from the live web (block explorers, APIs), validators on different LLM policies re-derive the verdict and vote. Takes 1–2 minutes; a couple of validator disagreements is normal, quorum decides.
5. Read the outcome: `get_escrow(escrow_id)` (status/verdict/confidence/evidence) and `get_verdict_log()` (full audit trail)
6. If PARTIAL: `appeal(escrow_id)` rewrites the condition into strict atomic checks → `resolve` again

### Local test suite (no Studio needed)

```bash
python -m venv .venv            # Python 3.12+ required
.venv\Scripts\pip install genlayer-test
.venv\Scripts\pytest tests/direct -v
```

11 tests run against an in-memory direct VM with mocked LLM/web: escrow lifecycle, beneficiary-only claims, RELEASE/REFUND flows, high-value confidence downgrade, leader-vs-jury disagreement, the full appeal → re-resolve loop, and funding guards. The direct VM also simulates `ExecPromptTemplate` (equivalence principles) and sandboxed validators, so validator logic is testable locally via `direct_vm.run_validator()`.

## Contract API (v0.1.0)

| Method | Type | Description |
|---|---|---|
| `create_escrow(condition, beneficiary, deadline)` | write, **payable** | Locks sent value; returns escrow id |
| `submit_claim(escrow_id, claim_text, claim_links)` | write | Beneficiary files the claim |
| `resolve(escrow_id)` | write | Runs the AI jury; settles RELEASE/REFUND, keeps PARTIAL locked |
| `appeal(escrow_id)` | write | After PARTIAL: rewrites condition into strict atomic checks, reopens resolution |
| `get_escrow(escrow_id)` | view | Full escrow state incl. verdict + evidence |
| `get_verdict_log()` | view | Append-only audit log of every arbitration round |

## Tech

- **GenLayer** Intelligent Contract (Python, GenVM)
- `gl.vm.run_nondet_unsafe` — custom leader/jury consensus
- `gl.nondet.exec_prompt` / `gl.nondet.web.get` — LLM reasoning + independent web evidence
- `gl.eq_principle.prompt_non_comparative` — appeal condition restatement

## Status & roadmap

- [x] v0.1.0 — contract with full leader/jury/appeal flow, payable escrow, verdict log
- [x] Deployed + verified end-to-end on GenLayer Studio (full consensus: create → claim → RELEASE with real web evidence → settlement; guards and audit log verified on-chain)
- [ ] Appeal loop demonstrated on-chain (PARTIAL → appeal → REFUND) — prompt rules updated, pending retest
- [ ] Multi-source evidence cross-checking (block explorer + archive API) with LLM adjudication on disagreement
- [ ] Per-condition evidence source registry (GitHub API, Etherscan, uptime monitors)
- [ ] Stake-weighted juror incentives and slashing for provably lazy validation
- [ ] Frontend: create / claim / resolve / appeal dashboard
