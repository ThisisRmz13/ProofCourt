# ProofCourt — Resume Notes (continue here tomorrow)

Last updated: 2026-09-14 (~9:00 PM session)
Repo: https://github.com/ThisisRmz13/ProofCourt (branch `main`)
Project: AI-jury escrow arbitration on GenLayer (Leader / Compare / Appeal prompts).

---

## 1. Where we are RIGHT NOW

### ✅ MILESTONE (2026-09-14 ~8:30 PM): FULL E2E SUCCESS ON STUDIO
Contract `contracts.py` (same code as repo `contract.py`) deployed at `0xD8Ec0F2f90Ad38a63333AF4123AE52107941Ae9E`.
Full flow verified on-chain in Normal (Full Consensus) mode:
`create_escrow` → `submit_claim` → `resolve` → **RELEASED, verdict RELEASE, confidence 0.96**,
leader fetched real evidence (Blockstream API, block 800000, ts 2024), validators agreed (3/4, 1 disagree → quorum OK),
`emit_transfer` settlement succeeded after funding the contract.
**Funding lesson: the contract needs balance** — sent 2 GEN from wallet to the contract address (tx `0x3cb45...42bb6`); escrow amount is raw units (100), so dust suffices. First resolve attempt failed with `SystemError: 7: inbalance` (zero balance) — this is the §5.4 payable gap, workaround = fund the contract manually.
Also observed once: pre-funding resolve reached consensus but rolled back at emit_transfer (verdict lost) — expected, rollback is atomic.
Studio flakiness (§5.1) confirmed in the wild: some validators Disagree with "leader verdict was not valid JSON" — quorum still reached, retry not needed when ≥ quorum Agree.

### Studio (hosted, network = "GenLayer" localnet — NOT Bradbury)
- OLD instance `0x86...bbC6` (pre-emit_transfer code) is obsolete — use `0xD8Ec0F2f90Ad38a63333AF4123AE52107941Ae9E`
- `escrow-1`: **RELEASED / RELEASE / 0.96** ✅ + `get_verdict_log` verified (full audit record on-chain) ✅
- `escrow-2` ("The Bitcoin network is healthy"): resolve → LLM gave a DECISIVE verdict (not PARTIAL — LLMs find ways to verify vague conditions). Then `appeal` → correctly rejected ("only after PARTIAL") and second `resolve` → correctly rejected ("not awaiting resolution"). **Guards work; no bug.** Lesson: PARTIAL only comes with genuinely incomplete evidence.
- To demo PARTIAL→appeal on Studio, use escrow-3 condition: `Bitcoin block 800000 exists on the blockchain, AND the beneficiary received a 0.1 BTC payment from Satoshi's genesis wallet (no transaction hash is provided)` — half provable, half not → expect PARTIAL (partial_details asks for tx hash) → `appeal` → re-`resolve` → expect REFUND.
- `test_min.py` deploys fine (smoke test for the environment)

### Hackathon submission readiness (assessed 2026-09-14)
1. 🔴 **Fund-locking (§5.4)** — create_escrow locks NOTHING; anyone can create arbitrary-amount escrow and drain contract balance. MUST restore payable before submission. NEXT ACTION: run `test_payable.py` locally, figure out why Studio schema parser rejected the decorator.
2. 🟡 Appeal path on Studio not yet demonstrated (local test green) — use the escrow-3 condition above.
3. 🟡 README.md stale (describes payable + old storage).
4. 🟡 Two-account demo video (payer ≠ beneficiary, bogus claim → REFUND).
5. 🟢 Frontend optional (Next.js boilerplate + genlayer-js) — contract + Studio demo usually enough.

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

1. ~~🔴 Fund-locking~~ **FIXED 2026-09-14 night**: `create_escrow` is `@gl.public.write.payable` again, amount = `gl.message.value` (no amount param). Root cause of the old Studio schema rejection was almost certainly the `beneficiary: Address` param (Studio sends ints), NOT payable — old payable version (d31fe7f~1) also had a stray `# v0.1.0` second line. Local `get_schema` accepts payable=True (verified) + `test_payable.py` needed `__init__` (added). Direct tests: 11/11 green incl. new `test_create_escrow_requires_funding`. STILL NEEDS: deploy fresh Studio instance and confirm the payable form (Value field) works on-chain.
2. **`resolve` UNDETERMINED / validator disagreement on hosted Studio** — different LLM policies occasionally produce "leader verdict was not valid JSON" on their side; quorum usually still reached. Mitigations if needed: lenient compare tolerance in `validator_fn`, clearer prompt format instructions, retries.
3. ~~`gl.eth.send(Address, u256)` unverified~~ **RESOLVED**: official API is `gl.get_contract_at(addr).emit_transfer(value=u256(...))` — verified ON-CHAIN (settlement succeeded 2026-09-14).
4. **README.md is stale** — still describes payable create_escrow and old storage; update after fund-locking decision (§5.1).
5. **glsim for consensus-like local testing** (optional): `pip install genlayer-test[sim]` then `glsim --port 4000 --validators 5`.

---

## 6. Later roadmap (after MVP demo works end-to-end)

- Frontend (Next.js boilerplate `frontend/` from genlayer-project-boilerplate + genlayer-js; connect to Studio localnet RPC `http://localhost:4000/api` or deployed instance)
- Two-account demo video: payer creates escrow, separate beneficiary claims, jury refunds a bogus claim (deception test), appeal → release flow
- Multi-source evidence cross-check (block explorer + archive API) with LLM tie-break inside leader_fn
- Bradbury testnet last (needs real GEN from faucet, pinned runner id, real validators — slower and noisier)
- Optional: genvm-lint in CI (`pip install genvm-linter`, `genvm-lint check contract.py`)

---

## 7. Quick-start next session (copy-paste block)

```powershell
cd C:\Users\Asus\Desktop\git\ProofCourt
git status
.venv\Scripts\pytest tests/direct -v          # expect: 10 passed
# THEN the main task — fund-locking (§5.1):
#  1. inspect test_payable.py, run it locally against the direct VM
#  2. try @gl.public.write.payable on a minimal contract for the Studio schema parser
#  3. if OK: restore payable create_escrow, update tests, deploy fresh Studio instance
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
