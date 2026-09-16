# ProofCourt — Resume Notes (continue here tomorrow)

Last updated: 2026-09-15 session
Repo: https://github.com/ThisisRmz13/ProofCourt (branch `main`, all pushed)
Project: AI-jury escrow arbitration on GenLayer (Leader / Compare / Appeal prompts).

---

## 0. ⚠️ BLOCKER: Studio Next (Studio Dev) is BROKEN — not our code (2026-09-15)

The hackathon form requires a Studio Next (chain 61997) deployment, but **Studio Dev cannot load ANY contract right now** — `gen_getContractSchemaForCode` fails with `invalid_contract runner malformed` for every file (even t0 minimal and GenLayer's own example). Root cause: GenVM v0.3.0-rc7 on Studio Dev cannot load the registered py-genlayer runner (`chain:0x0:d:q805cc3...`).
- Confirmed upstream: genlayer-studio issue **#1757** "Studio Dev rejects its own v0.3 contract during schema extraction" (open since 2026-09-04, no response) + related #1762 (legacy v0.2 contract compatibility).
- Bisect artifacts saved in `tests/next/t0*.py`, `t1_basic.py`, `t2_payable.py`, `t3_storage.py` (all pass local schema check).
- **ACTION: retry the Studio Next deploy daily** (paste contract.py → deploy). The moment issue #1757 is fixed, deployment takes 5 minutes.
- Fallback for the form meanwhile: use the hosted-Studio instance link (`0xB5FA28f768FcB575cf20a61153e4cf1F4E7A92eb` — full cycle verified there) and reference issue #1757 as proof the Studio Next blocker is upstream, not the project.

---

## 0b. ✅ FULL CYCLE VERIFIED ON-CHAIN (2026-09-15) — MVP IS COMPLETE

- **PRIMARY INSTANCE (fixed code, case-insensitive beneficiary): `0xE0Fc7D30ccb0e4b89cB3Bfb60524783C76bd9E65`** — deployed 2026-09-16, fix verified via gen_getContractCode. escrow-1 → RELEASE 0.95 (blockstream evidence) already on-chain. Default address in try.html.
- Other instances: `0x15Ba…ce27` (fixed code, escrow-1 = full PARTIAL→appeal→RELEASE 0.96 arc) and `0xB5FA…92eb` (old code, legacy history). All on hosted Studio.
- Legacy instance `0xB5FA28f768FcB575cf20a61153e4cf1F4E7A92eb` — old code (pre case-fix), holds the fully verified cycle (escrow-1 PARTIAL→appeal→re-resolve, escrow-2 REFUND, guards) + ~10 dust escrows of 1 GEN. Keep as the form's how-to link (its on-chain history is the proof) OR switch links to the new instance. Upgrade code on it FAILS with "Only contract deployer can upgrade" (Studio quirk) — that's why the fresh instance exists.

## 0c. 🎉 WEBSITE WRITE PATH VERIFIED (2026-09-15 night)

**COMPLETE LITIGATION ARC FROM THE FRONTEND (2026-09-16) — the flagship demo:**
On instance `0x15Ba…ce27`, entirely from `proofcourt.pages.dev/try`:
create_escrow (1 GEN locked) → submit_claim (CLAIMED) → resolve#1 → **PARTIAL 0.15** ("cannot verify — do not guess") → appeal → condition rewritten into 3 atomic binary checks (appeal_round 1) → resolve#2 → **RELEASE 0.96** (block 800000, ts < 2025-01-01) — funds released. The 0.15 → appeal → 0.96 arc is the core ProofCourt story for the demo video.

The Live courtroom page (`proofcourt.pages.dev/try`) creates escrows ON-CHAIN with a connected wallet:
- `create_escrow` with Value=1 GEN succeeded multiple times from the browser (wallet + genlayer-js). Confirmed by reading the chain with a local Node script (genlayer-js): **escrow-3 … escrow-11 all OPEN, 1 GEN each** (user clicked repeatedly because the page mis-detected success).
- Fixes shipped: BigInt.toJSON polyfill (wallet tx serialization), receipt success detection (genlayer-js simplified receipt has NO txExecutionResultName; execution result lives in `consensus_data.leader_receipt[0].execution_result` = "SUCCESS"; returned escrow id findable via /"escrow-\d+"/ in the receipt JSON).
- Cleanup TODO (optional): 9 dust escrows (1 GEN each) sit OPEN on `0xB5FA…92eb` — resolving them from Studio (payer == beneficiary) returns the 1 GEN each. Harmless either way.
- Demo script for the site: open /try → state auto-loads → create escrow (Value 1) → **✓ finalized** → Read escrow → live on-chain state. Writes via site, jury via Studio, everything on-chain. **CONFIRMED WORKING END-TO-END (2026-09-15 night): create_escrow from the page returned "✓ finalized" with the fixed receipt detection; escrow-12 created.**

Instance `0xB5FA28f768FcB575cf20a61153e4cf1F4E7A92eb` (deployed from latest code with new prompt rules):
- escrow-1 (genesis-wallet condition, Value 100 GEN): resolve round 0 → **PARTIAL 0.25** (new rules work: "cannot verify" ≠ REFUND; reasoning literally cites the rule) → `appeal` → condition rewritten to 3 atomic binary checks (`appeal_round: 1`, `revised_checks` populated) → resolve round 1 (tx `0x2bbd`) → **PARTIAL 0.0 SUCCESS** (honest: leader has NO live web access). Final state: PARTIAL, funds still locked.
- escrow-2 (same condition): resolve → **REFUND 0.98** (different LLM used affirmative training-knowledge contradiction: genesis wallet never spent) → closed, funds returned.
- Guards verified: `appeal` without PARTIAL → rejected; `resolve` on closed escrow → rejected ("escrow is not awaiting resolution", MAJORITY_AGREE).
- **Demo gold**: same condition → PARTIAL 0.25 (one LLM) vs REFUND 0.98 (another) — perfect illustration of why multi-validator consensus is needed.
- Key product insight: the leader LLM has no live web in hosted Studio; **`claim_links` is the only real evidence channel** (contract fetches them via `web.render` and inlines into the prompt). Earlier "Blockstream API" evidence quotes were LLM hallucinations (timestamps inconsistent across runs). For a RELEASE demo, submit a claim WITH a real link (e.g. `https://mempool.space/api/block-height/800000`).

## 1. Where we are RIGHT NOW

### ✅ MILESTONE (2026-09-14): FULL E2E ON STUDIO, TWICE
- Instance `0xe1...80ED` (full address in Studio panel) — **payable contract deployed successfully** (deploy tx `0x1f2d` SUCCESS, validators agreed). UI marks `create_escrow payable` with a Value field.
- escrow-1: Value `100` → stored as `100000000000000000000` wei (Studio converts GEN→wei) → `RELEASED / RELEASE / confidence 1.0`. Fund-locking works end-to-end. NO manual contract funding needed anymore (payer locks per-escrow).
- Earlier instance `0xD8Ec0F2f90Ad38a63333AF4123AE52107941Ae9E` (pre-payable code, manually funded with 2 GEN) — also fully verified (RELEASE 0.96 + verdict_log audit). Both obsolete now except as reference.
- `escrow-2` on 0xe1 instance (genesis-wallet condition): resolve → REFUND 0.85 under OLD prompt rules → appeal correctly rejected (guard). Retest with new rules (§0.3).
- Observations: LLM verdict variance is real (block timestamp hallucinated differently across runs: 2023-09-09 / 2024-05-23 / 2024-09-14) — good talking point for multi-validator design. Studio UI quirk: after deploy SUCCESS the panel may say "Not deployed yet" until F5 refresh.
- LLM note: validators are policy-routed (sonnet/gemini/mistral/gpt-oss/gpt-5-4/grok/gemma/claude...); 1-2 Disagrees per round are normal, quorum always reached.

### Studio (hosted, network = "GenLayer" localnet — NOT Bradbury)
- ACTIVE instance: `0xe1...80ED` (payable code). Old ones obsolete.
- `escrow-1`: RELEASED/RELEASE/1.0 ✅ (fund-locking verified)
- `escrow-2`: REFUNDED under old rules (see §0)
- **Pending on-chain demo**: PARTIAL → `appeal` → REFUND with new prompt rules (§7)
- Suggested condition for the appeal demo: `Bitcoin block 800000 exists on the blockchain, AND the beneficiary received a 0.1 BTC payment from Satoshi's genesis wallet (no transaction hash is provided)` — with NEW rules this must be PARTIAL (genesis wallet payment = cannot verify, not contradiction)
- `test_min.py` deploys fine (smoke test for the environment)

### Hackathon submission readiness (updated 2026-09-15)
1. ✅ Fund-locking — DONE & verified on-chain (payable Value field)
2. ✅ Appeal loop on-chain — DONE (PARTIAL → atomic rewrite → re-resolve; guards verified)
3. ✅ README — updated (Run-it guide, verified status, fairness rule)
4. 🟡 Two-account demo video (payer ≠ beneficiary; bogus claim → REFUND; appeal flow) — NEXT
5. 🟢 Optional: escrow with real `claim_links` → RELEASE demo (the evidence channel)
6. 🟢 Frontend (Next.js boilerplate + genlayer-js) — only if time allows

### Local test suite (NEW — this is our debugging engine now)
- venv: `.venv` (Python **3.12.10** — genlayer-test needs >= 3.12; 3.11 fails on `collections.abc.Buffer`)
- `genlayer-test==0.29.2`, direct mode (in-memory, LLM/web mocked, no Studio needed)
- Run: `.venv\Scripts\pytest tests/direct -v`
- Last run: **10 passed, 0 failed — ALL GREEN** ✅
- Tests cover: create, beneficiary-only claim, RELEASE, REFUND, high-value downgrade, leader/compare disagreement (validator vote via `direct_vm.run_validator()`), full appeal→re-resolve, guards

---

## 2. RESOLVED — the bug that was being fixed (2026-09-14 late night session)

All fixed and committed:

1. **`_resolve()` helper** in `contract.py` — handles Lazy vs dict vs str from `exec_prompt`/`web.render`/`prompt_non_comparative` (real GenVM returns Lazy, must `.get()`).
2. **confidence → str before crossing nondet boundary** — float is NOT calldata-encodable (trace: `gl_call encode error: not calldata encodable 0.95: float`). Leader_fn now normalizes `data["confidence"] = str(_to_float(...))`. Never put floats in dicts returned from nondet blocks.
3. **`gl.eth.send` does NOT exist in the real SDK** → replaced with the official API:
   `gl.get_contract_at(Address(...)).emit_transfer(value=u256(amount))` (sends `PostMessage`). Confirmed in extracted SDK source (`genvm_contracts.py`). In direct mode it's a no-op (trace shows `Unknown gl_call request type: ['PostMessage']`) — settlement must be verified on Studio.
4. **`appeal` needed `_resolve()` too** — `prompt_non_comparative` returns Lazy (via `run_nondet.lazy`).
5. **direct VM extensions in `tests/direct/conftest.py`** (monkeypatches on `gltest.direct.wasi_mock`):
   - `ExecPromptTemplate` handled: Leader template → LLM mock on task+input+criteria; `EqNonComparativeValidator`/`EqComparative` → `{"ok": True}` (genvm decides, direct mode always agrees)
   - `Sandbox` gl_call actually executes the cloudpickled fn (needed by eq_principle validator paths)
6. **loader replaces `run_nondet*` entirely in direct mode** (leader-only, validators captured) → to test validator logic locally use `direct_vm.run_validator()` (official API). The disagreement test asserts `run_validator() is False`; end-to-end blocking is only verifiable on Studio/consensus.
7. **`mock_llm` accumulates, first match wins** → `_setup_leader_verdict` now calls `direct_vm.clear_mocks()` first (stale-mock bug made re-resolve reuse the old PARTIAL verdict).

---

## 3. Hard-won GenLayer rules (DO NOT regress — each cost hours)

1. **Line 1 of the file MUST be exactly:**
   `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`
   (hash taken from official boilerplate `contracts/football_bets.py`). `"latest"` breaks hosted Studio; the comment must be the FIRST line or you get `invalid_contract absent_runner_comment`.
2. **Studio schema parser rejects** (→ "Could not load contract schema" / `invalid_contract`):
   - nested `@allow_storage @dataclass` as storage values → we store **JSON strings** instead (`TreeMap[str, str]`, `DynArray[str]`)
   - `@gl.public.write.payable` decorator → removed; fund-locking must come back differently (see §6). Isolate with `test_payable.py`.
3. **Studio UI sends wallet addresses as giant ints**, not hex → all address-ish params are plain `str` in our ABI (e.g. `create_escrow.beneficiary: str`, stored via `.as_hex` of sender).
4. **float in calldata = hard error.** Use str/int only in anything crossing nondet boundaries.
5. **Direct mode `run_nondet_unsafe` = leader_fn only** (validators are skipped) → validator/consensus logic can ONLY be verified on Studio/localnet.
6. **Windows quirk:** gltest direct loader crashes (`PermissionError` unlinking temp stdin file). Workaround lives in `tests/direct/conftest.py` (monkeypatched `os.unlink`). Keep it.
7. `exec_prompt` result shapes: real GenVM = Lazy (call `.get()`); direct mode = dict or str; `_resolve()` handles all.

---

## 4. What to do in Studio (current playbook)

1. Instance: `0xD8Ec0F2f90Ad38a63333AF4123AE52107941Ae9E` (funded with 2 GEN — enough for many dust-amount escrows)
2. Fresh escrow needs: `create_escrow` → `submit_claim` → `resolve` (Normal/Full Consensus; wait FINALIZED; LLMs may take 1–2 min)
3. Read outcomes: `get_escrow(escrow-N)` (status/verdict/confidence/evidence/partial_details), `get_verdict_log()`
4. **Simulation Mode** toggle = fast raw errors without consensus (state changes usually NOT persisted — dry-run)
5. Finalized + ERROR = deterministic rollback (guards or settlement failure); FINALIZED + SUCCESS = applied
6. If a tx hits `SystemError: 7: inbalance` → contract is out of funds, send more GEN from wallet

When pasting from GitHub: always Raw → Ctrl+A → Ctrl+C; make sure file is fully cleared first (a duplicated paste caused one false alarm).

---

## 5. Known open issues (priority order)

1. ~~🔴 Fund-locking~~ **DONE** — payable restored & verified on-chain (2026-09-14). Schema-check tooling: local `get_schema` (from extracted SDK) + `load_contract_class` + wasi injection + `os.unlink` Windows patch — see session notes in §2/§7.
2. **Appeal path on-chain** — new "cannot verify = PARTIAL" prompt rules pushed (`406f4fa`), verify tomorrow with the genesis-wallet escrow (§7). If LLM STILL says REFUND, next lever: make the rule even more explicit or add an example to LEADER_PROMPT.
3. **README.md stale** — rewrite: current payable flow, Studio instructions (Value field!), local test setup, architecture table already fine.
4. **Validator disagreement noise** — normal, quorum reached in practice; revisit only if a resolve ends UNDETERMINED twice in a row.
5. **glsim for consensus-like local testing** (optional): `pip install genlayer-test[sim]` then `glsim --port 4000 --validators 5`.

---

## 6. Later roadmap (after MVP demo works end-to-end)

- Frontend (Next.js boilerplate `frontend/` from genlayer-project-boilerplate + genlayer-js; connect to Studio localnet RPC `http://localhost:4000/api` or deployed instance)
- Two-account demo video: payer creates escrow, separate beneficiary claims, jury refunds a bogus claim (deception test), appeal → release flow
- Multi-source evidence cross-check (block explorer + archive API) with LLM tie-break inside leader_fn
- Bradbury testnet last (needs real GEN from faucet, pinned runner id, real validators — slower and noisier)
- Optional: genvm-lint in CI (`pip install genvm-linter`, `genvm-lint check contract.py`)

---

## 7. Quick-start tomorrow (copy-paste block)

```powershell
cd C:\Users\Asus\Desktop\git\ProofCourt
git pull
.venv\Scripts\pytest tests/direct -v          # expect: 11 passed
# TASK 1 — verify new prompt rules on-chain (appeal demo):
#   Studio: paste latest contract.py -> Upgrade code (instance 0xe1...80ED keeps state)
#   create_escrow: condition=genesis-wallet condition (§1), beneficiary=wallet, deadline=2026-10-01, Value=50
#   submit_claim -> resolve  =>  expect PARTIAL (partial_details says what evidence closes the gap)
#   appeal -> resolve        =>  expect REFUND
# TASK 2 — rewrite README.md (payable flow, Value field, local tests, architecture)
# TASK 3 — two-account demo video (payer != beneficiary; bogus claim -> REFUND; appeal -> release)
```

Studio playbook: §4. Open issues: §5.

---

## File map

```
contract.py                     # the ProofCourt contract (JSON-string storage)
test_min.py                     # env smoke test
test_payable.py                 # isolate @gl.public.write.payable support (NEXT TASK)
tests/direct/conftest.py        # Windows unlink patch + ExecPromptTemplate/Sandbox direct-VM patches (required!)
tests/direct/test_proofcourt.py # 10 scenario tests with LLM mocks (9 core + disagreement)
tests/direct/test_debug.py      # trace-printer (keep, useful)
continue.md / README.md / LICENSE / .gitignore
```
