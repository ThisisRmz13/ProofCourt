# ProofCourt — Resume Notes (continue here tomorrow)

Last updated: 2026-09-14 (late night session)
Repo: https://github.com/ThisisRmz13/ProofCourt (branch `main`)
Project: AI-jury escrow arbitration on GenLayer (Leader / Compare / Appeal prompts).

---

## 1. Where we are RIGHT NOW

### Studio (hosted, network = "GenLayer" localnet — NOT Bradbury)
- `contract.py` is DEPLOYED at `0x86...bbC6` ✅ (schema loads, Run & Debug panel works)
- `escrow-1` created (`create_escrow` FINALIZED) — condition: "Bitcoin block 800000 exists on the Bitcoin blockchain and was mined before 2025", payer = beneficiary = `0xd32cdB39d204b3945496Fed07c3096067F14F613`, amount `"100"`, status `OPEN`
- `submit_claim` FINALIZED ✅
- `resolve` #1 (tx `0xb27f...`) FINALIZED — **outcome unknown, check `get_escrow` first thing**
- `resolve` #2 (tx `0xdf98...`) ended **UNDETERMINED** (validators could not reach consensus — see §5)
- `test_min.py` deploys fine (smoke test for the environment)

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

## 4. What to do in Studio after local tests are green

1. Select the deployed instance `0x86...bbC6` (or **Deploy new instance** from the updated `contract.py`)
2. `get_escrow(escrow-1)` → read the outcome of the earlier `resolve` (status: CLAIMED? PARTIAL? RELEASED/REFUNDED? check `verdict`, `confidence`, `evidence_summary`, `partial_details`)
3. If still `CLAIMED`: try `resolve` again — hosted Studio sometimes ends `UNDETERMINED` due to validator flakiness, retry may pass
4. If `PARTIAL`: run `appeal` → then `resolve` again (appeal rewrites condition into atomic checks)
5. If `RELEASED`/`REFUNDED`: check `get_verdict_log()` and — if it got that far — whether the GEN balance moved (see §5 #3)
6. Use **Simulation Mode** toggle to get fast, raw error messages without consensus

When pasting from GitHub: always Raw → Ctrl+A → Ctrl+C; make sure file is fully cleared first (a duplicated paste caused one false alarm).

---

## 5. Known open issues (priority order)

1. **`resolve` UNDETERMINED on hosted Studio** — leader + validators each run their own LLM (GPT/Gemini/Qwen/DeepSeek...) on the Leader+Compare prompts; disagreement is expected. Mitigations to try: make compare tolerance more lenient in `validator_fn` (currently requires exact same verdict), lower prompt ambiguity, or accept retries.
2. **Hosted-Studio validator flakiness** — during consensus rounds, many validators die with `SystemError: 6: forbidden` in `root_slot.lock_default()` / "absent_runner_comment" on appeals. This is THEIR infrastructure, not our code. Local direct tests + GLSim are the reliable path; consider `pip install genlayer-test[sim]` and run `glsim --port 4000 --validators 5` locally for consensus-like testing without Studio.
3. ~~`gl.eth.send(Address, u256)` unverified~~ **RESOLVED**: official API is `gl.get_contract_at(addr).emit_transfer(value=u256(...))`. Direct mode no-ops it; still needs on-chain verification (contract must hold balance — see #4).
4. **Payable / real fund lock removed** (Studio schema rejected the decorator). Re-test `test_payable.py` in isolation; if payable works, switch `create_escrow` back to `@gl.public.write.payable` + `gl.message.value` and drop the `amount: str` param.
5. **README.md is stale** — still describes payable create_escrow and old storage; update after §5.3/§5.4 decisions.

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
git status                          # see the uncommitted contract.py fix + tests
.venv\Scripts\pytest tests/direct -v          # goal: 9 passed
# if needed:
.venv\Scripts\pytest tests/direct/test_debug.py -v -s   # shows vm traces
# when green:
git add -A && git commit -m "direct tests green + lazy-resolve + calldata-safe confidence" && git push
```
Then Studio: `get_escrow(escrow-1)` → continue flow (§4).

---

## File map

```
contract.py                    # the ProofCourt contract (JSON-string storage)
test_min.py                    # env smoke test
test_payable.py                # isolate @gl.public.write.payable support
tests/direct/conftest.py       # Windows unlink monkeypatch (required!)
tests/direct/test_proofcourt.py# 9 scenario tests with LLM mocks
tests/direct/test_debug.py     # trace-printer (temporary)
README.md / LICENSE / .gitignore
```
