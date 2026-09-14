import json

from genlayer_py.types.calldata import CalldataAddress


CONTRACT = "contract.py"

LEADER_MARK = "impartial arbitration validator"
COMPARE_MARK = "verification validator"
APPEAL_MARK = "Rewrite the condition"


def _addr(addr) -> str:
    return CalldataAddress(addr).as_hex


def _leader_response(verdict, confidence):
    return json.dumps(
        {
            "verdict": verdict,
            "confidence": str(confidence),
            "evidence_summary": "Verified block explorer data directly.",
            "reasoning": "Condition elements checked against on-chain facts.",
            "partial_details": "some gap" if verdict == "PARTIAL" else "",
        }
    )


def _compare_response(verdict):
    return json.dumps(
        {
            "vote": "SIMILAR",
            "confidence": "0.9",
            "your_verdict": verdict,
            "disagreement_reason": "",
        }
    )


def _appeal_response():
    return json.dumps(
        {
            "revised_condition": "Bitcoin block 800000 is confirmed by a block explorer",
            "checks": [
                "block explorer returns data for block 800000",
                "block 800000 timestamp is before 2025-01-01",
            ],
            "verifiable_from": "public block explorer API",
        }
    )


def _setup_leader_verdict(direct_vm, verdict, confidence):
    direct_vm.clear_mocks()
    direct_vm.mock_llm(LEADER_MARK, _leader_response(verdict, confidence))
    direct_vm.mock_llm(COMPARE_MARK, _compare_response(verdict))


def _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob, amount="100"):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    escrow_id = contract.create_escrow(
        "Bitcoin block 800000 exists and was mined before 2025",
        _addr(direct_bob),
        "2026-10-01",
        amount,
    )
    return contract, escrow_id


def test_create_escrow_opens_state(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, escrow_id = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob)
    assert escrow_id == "escrow-1"
    state = json.loads(contract.get_escrow("escrow-1"))
    assert state["status"] == "OPEN"
    assert state["beneficiary"] == _addr(direct_bob)
    assert state["amount"] == "100"
    assert json.loads(contract.get_verdict_log()) == []


def test_only_beneficiary_can_claim(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract, _ = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.sender = direct_charlie
    with direct_vm.expect_revert("only the beneficiary can submit a claim"):
        contract.submit_claim("escrow-1", "I did it", "")
    direct_vm.sender = direct_bob
    contract.submit_claim("escrow-1", "I did it", "")
    state = json.loads(contract.get_escrow("escrow-1"))
    assert state["status"] == "CLAIMED"
    assert state["claim_text"] == "I did it"


def test_resolve_release(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, _ = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    contract.submit_claim("escrow-1", "Condition satisfied", "")
    _setup_leader_verdict(direct_vm, "RELEASE", 0.95)
    contract.resolve("escrow-1")
    state = json.loads(contract.get_escrow("escrow-1"))
    assert state["status"] == "RELEASED"
    assert state["verdict"] == "RELEASE"
    log = json.loads(contract.get_verdict_log())
    assert len(log) == 1
    assert log[0]["stage"] == "resolve"
    assert log[0]["verdict"] == "RELEASE"


def test_resolve_refund(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, _ = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    contract.submit_claim("escrow-1", "Condition satisfied", "")
    _setup_leader_verdict(direct_vm, "REFUND", 0.9)
    contract.resolve("escrow-1")
    state = json.loads(contract.get_escrow("escrow-1"))
    assert state["status"] == "REFUNDED"


def test_high_value_low_confidence_release_downgrades_to_partial(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, _ = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob, amount="5000")
    direct_vm.sender = direct_bob
    contract.submit_claim("escrow-1", "Condition satisfied", "")
    _setup_leader_verdict(direct_vm, "RELEASE", 0.75)
    contract.resolve("escrow-1")
    state = json.loads(contract.get_escrow("escrow-1"))
    assert state["status"] == "PARTIAL"
    assert "Downgraded" in state["partial_details"]


def test_leader_compare_disagreement_rejected_by_validator(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, _ = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    contract.submit_claim("escrow-1", "Condition satisfied", "")
    direct_vm.mock_llm(LEADER_MARK, _leader_response("RELEASE", 0.95))
    direct_vm.mock_llm(COMPARE_MARK, _compare_response("PARTIAL").replace('"vote": "SIMILAR"', '"vote": "DIFFERENT"'))
    contract.resolve("escrow-1")
    assert direct_vm.run_validator() is False


def test_appeal_rewrites_condition_and_re_resolves(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract, _ = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    contract.submit_claim("escrow-1", "Condition satisfied", "")
    _setup_leader_verdict(direct_vm, "PARTIAL", 0.8)
    contract.resolve("escrow-1")
    state = json.loads(contract.get_escrow("escrow-1"))
    assert state["status"] == "PARTIAL"

    direct_vm.mock_llm(APPEAL_MARK, _appeal_response())
    contract.appeal("escrow-1")
    state = json.loads(contract.get_escrow("escrow-1"))
    assert state["status"] == "APPEALED"
    assert "block explorer" in state["condition"]
    assert int(state["appeal_round"]) == 1
    checks = json.loads(state["revised_checks"])
    assert len(checks) == 2

    _setup_leader_verdict(direct_vm, "RELEASE", 0.95)
    contract.resolve("escrow-1")
    state = json.loads(contract.get_escrow("escrow-1"))
    assert state["status"] == "RELEASED"
    log = json.loads(contract.get_verdict_log())
    stages = [entry["stage"] for entry in log]
    assert stages == ["resolve", "appeal", "resolve"]


def test_cannot_resolve_without_claim(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, _ = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob)
    with direct_vm.expect_revert("escrow is not awaiting resolution"):
        contract.resolve("escrow-1")


def test_cannot_appeal_before_partial(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, _ = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob)
    with direct_vm.expect_revert("appeal is only available after a PARTIAL verdict"):
        contract.appeal("escrow-1")
