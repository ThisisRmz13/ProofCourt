import json

from test_proofcourt import (
    _create_escrow,
    _leader_response,
    _setup_leader_verdict,
)


def test_debug_trace(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract, _ = _create_escrow(direct_vm, direct_deploy, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    contract.submit_claim("escrow-1", "x", "")
    _setup_leader_verdict(direct_vm, "RELEASE", 0.95)
    try:
        contract.resolve("escrow-1")
    except Exception as e:
        print("CAUGHT:", type(e).__name__, e)
    print("=== TRACES ===")
    for t in direct_vm._traces:
        print(t)
