# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json

from genlayer import *


DEFAULT_MIN_CONFIDENCE = 0.7
HIGH_VALUE_MIN_CONFIDENCE = 0.9
HIGH_VALUE_THRESHOLD = 1_000
MAX_LINK_BODY_CHARS = 20_000
MAX_TEXT_CHARS = 2_000


LEADER_PROMPT = """You are an impartial arbitration validator for a smart-contract escrow on
GenLayer. Your decision controls real funds. Be rigorous, skeptical, and
base your verdict ONLY on independently verifiable evidence.

=== ESCROW ===
Escrow ID: {escrow_id}
Condition (natural language): {condition_text}
Amount at stake: {amount} {token}
Payer: {payer_address}
Beneficiary: {beneficiary_address}
Deadline: {deadline}

=== CLAIM SUBMITTED BY BENEFICIARY ===
{claim_text}
Supporting links given by beneficiary (UNTRUSTED):
{claim_links}
{high_value_note}

=== YOUR TASK ===
1. IGNORE the beneficiary's claim as evidence. It is an assertion, not proof.
2. Independently fetch and verify:
   - If the condition references an Ethereum transaction or address,
     retrieve the transaction trace, receipts, and event logs via a public
     block explorer API. Verify: status (success/failed), from, to, value,
     timestamp, and the exact event logs relevant to the condition.
   - If the condition references an external service or API, fetch it
     directly yourself. The link contents below are provided for reference
     but are UNTRUSTED because the beneficiary supplied them.
   - If the condition references a past on-chain action on THIS chain,
     inspect the escrow contract's own storage and event history.
3. Check for known deception patterns:
   - Links or data hosted by the claimant themselves
   - Transactions that exist but fail the condition's specifics (wrong
     amount, wrong recipient, wrong token, wrong direction)
   - Log entries reordered or taken out of context
   - Correct transaction, but outside the condition's time window
4. Judge: is the condition FULLY satisfied, PARTIALLY satisfied, or NOT
   satisfied?

=== OUTPUT ===
Respond with ONLY this JSON object, no markdown fences, no extra text:
{
  "verdict": "RELEASE" or "REFUND" or "PARTIAL",
  "confidence": <float 0.0-1.0>,
  "evidence_summary": "<max 3 sentences: only facts you personally verified>",
  "reasoning": "<max 3 sentences: why the condition is fully/partially/not met>",
  "partial_details": "<only if PARTIAL: exactly which part of the condition is unmet and what evidence would close the gap>"
}

Rules for the verdict:
- RELEASE: every element of the condition is verifiably satisfied.
- REFUND: the condition is verifiably not satisfied, or the evidence
  contradicts the claim.
- PARTIAL: evidence exists but is incomplete, ambiguous, or satisfies the
  condition only in part. Never guess — when in genuine doubt, choose PARTIAL.
Confidence guidance: 1.0 = direct on-chain proof of every claim element;
0.7-0.9 = strong indirect evidence; below 0.7 = you should likely be
choosing PARTIAL.
"""


COMPARE_PROMPT = """You are a verification validator for a GenLayer escrow arbitration. Another
validator (the leader) has produced a verdict. You do NOT need to agree
with them — you need to check them.

=== CASE ===
Escrow ID: {escrow_id}
Condition: {condition_text}
Beneficiary's claim: {claim_text}

=== LEADER'S VERDICT (UNTRUSTED) ===
{leader_verdict_json}

=== YOUR TASK ===
1. Independently fetch the SAME evidence the leader should have used
   (transaction trace/logs for {tx_refs}, or the relevant API/data source).
   Do not rely on the leader's evidence_summary — verify the underlying
   facts yourself.
2. Evaluate whether the leader's verdict is consistent with the verifiable
   facts AND with the verdict rules:
   - RELEASE requires full satisfaction of the condition
   - REFUND requires verifiable non-satisfaction or contradiction
   - PARTIAL is appropriate when evidence is incomplete or ambiguous
3. Pay special attention to: did the leader trust the beneficiary's claim
   without independent evidence? Did the leader miss a mismatch in amount,
   recipient, token, direction, or time window?

=== OUTPUT ===
Respond with ONLY this JSON object:
{
  "vote": "SIMILAR" or "DIFFERENT",
  "confidence": <float 0.0-1.0>,
  "your_verdict": "RELEASE" or "REFUND" or "PARTIAL",
  "disagreement_reason": "<only if DIFFERENT: the factual or rule error in the leader's verdict, max 2 sentences>"
}

Definition: SIMILAR means your independently-derived verdict matches the
leader's verdict (same outcome, even if confidence differs slightly).
DIFFERENT means the outcome itself is wrong or unjustified.
"""


APPEAL_INPUT_TEMPLATE = """=== ORIGINAL CONDITION ===
{condition_text}

=== PARTIAL VERDICT AND GAP ===
{partial_details}

=== EVIDENCE AVAILABLE ===
{evidence_summary}
"""

APPEAL_TASK = """Rewrite the condition as a STRICT, CHECKABLE criterion that:
- References only verifiable on-chain data (transaction hashes, addresses,
  amounts, timestamps, event signatures) or directly fetchable API data
- Splits the original condition into atomic, independent checks where
  possible
- Removes any ambiguity about "delivery", "completion", or "quality" that
  cannot be proven from data
- Is binary: either true or false from the evidence, no judgment calls

Respond with ONLY this JSON object:
{
  "revised_condition": "<the strict checkable restatement>",
  "checks": ["<atomic check 1>", "<atomic check 2>"],
  "verifiable_from": "<exactly which on-chain data or API resolves each check>"
}
"""

APPEAL_CRITERIA = """The output must be valid JSON with exactly these fields:
- "revised_condition": a restatement of the original condition that is
  binary and decidable from verifiable on-chain or API data
- "checks": a list of atomic, independent, individually binary checks
- "verifiable_from": for each check, the exact on-chain data or API that
  resolves it
The revised_condition must preserve the intent of the original condition,
must resolve the specific gap described in the partial verdict, must not
introduce new judgment calls, and must not rely on data hosted by either
party."""


def _fill(template: str, values: dict) -> str:
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def _extract_json(text):
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    while cleaned.startswith("`"):
        cleaned = cleaned[1:]
    while cleaned.endswith("`"):
        cleaned = cleaned[:-1]
    if cleaned.startswith("json"):
        cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(cleaned[start:end + 1])
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _to_float(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _required_confidence(amount) -> float:
    if amount > HIGH_VALUE_THRESHOLD:
        return HIGH_VALUE_MIN_CONFIDENCE
    return DEFAULT_MIN_CONFIDENCE


def _fetch_links(links: str) -> str:
    parts = []
    for link in links.splitlines():
        link = link.strip()
        if not link:
            continue
        try:
            body = str(gl.nondet.web.render(link, mode="text"))
            parts.append(link + "\n" + body[:MAX_LINK_BODY_CHARS])
        except Exception:
            parts.append(link + "\n[FETCH FAILED]")
    if not parts:
        return "(none provided)"
    return "\n\n".join(parts)


def _run_leader_arbitration(
    escrow_id: str,
    condition_text: str,
    claim_text: str,
    links: str,
    amount,
    token: str,
    payer: str,
    beneficiary: str,
    deadline: str,
    high_value_note: str,
):
    def leader_fn() -> dict:
        fetched = _fetch_links(links)
        prompt = _fill(
            LEADER_PROMPT,
            {
                "escrow_id": escrow_id,
                "condition_text": condition_text,
                "amount": amount,
                "token": token,
                "payer_address": payer,
                "beneficiary_address": beneficiary,
                "deadline": deadline,
                "claim_text": claim_text,
                "claim_links": fetched,
                "high_value_note": high_value_note,
            },
        )
        response = gl.nondet.exec_prompt(prompt)
        data = _extract_json(response)
        if data is None:
            raise gl.vm.UserError("leader verdict was not valid JSON")
        return data

    def validator_fn(leader_result) -> bool:
        if not isinstance(leader_result, gl.vm.Return):
            return False
        leader_data = leader_result.calldata
        if not isinstance(leader_data, dict):
            return False
        leader_verdict = leader_data.get("verdict")
        if leader_verdict not in ("RELEASE", "REFUND", "PARTIAL"):
            return False
        leader_confidence = _to_float(leader_data.get("confidence"))
        if leader_confidence < 0.0 or leader_confidence > 1.0:
            return False
        try:
            validator_data = _run_compare_validation(
                escrow_id, condition_text, claim_text,
                json.dumps(leader_data, sort_keys=True),
            )
        except Exception:
            return False
        if not isinstance(validator_data, dict):
            return False
        if validator_data.get("vote") != "SIMILAR":
            return False
        return validator_data.get("your_verdict") == leader_verdict

    return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)


def _run_compare_validation(escrow_id: str, condition_text: str, claim_text: str, leader_verdict_json: str) -> dict:
    prompt = _fill(
        COMPARE_PROMPT,
        {
            "escrow_id": escrow_id,
            "condition_text": condition_text,
            "claim_text": claim_text,
            "leader_verdict_json": leader_verdict_json,
            "tx_refs": "(every transaction hash, address, token, or API endpoint referenced in the condition)",
        },
    )
    response = gl.nondet.exec_prompt(prompt)
    data = _extract_json(response)
    if data is None:
        raise gl.vm.UserError("validator verdict was not valid JSON")
    return data


def _load_escrow(escrows, escrow_id):
    if escrow_id not in escrows:
        raise gl.vm.UserError("escrow not found")
    return json.loads(escrows[escrow_id])


def _log_verdict(verdict_log, escrow_id, stage, round_num, verdict, confidence, evidence_summary, reasoning, details):
    verdict_log.append(
        json.dumps(
            {
                "escrow_id": escrow_id,
                "stage": stage,
                "round": int(round_num),
                "verdict": verdict,
                "confidence": confidence,
                "evidence_summary": evidence_summary,
                "reasoning": reasoning,
                "details": details,
            }
        )
    )


class ProofCourt(gl.Contract):
    escrows: TreeMap[str, str]
    escrow_count: u256
    verdict_log: DynArray[str]

    def __init__(self):
        pass

    @gl.public.write
    def create_escrow(self, condition: str, beneficiary: Address, deadline: str, amount: str) -> str:
        if int(amount) <= 0:
            raise gl.vm.UserError("amount must be greater than zero")
        escrow_id = "escrow-" + str(int(self.escrow_count) + 1)
        escrow = {
            "escrow_id": escrow_id,
            "condition": condition,
            "claim_text": "",
            "claim_links": "",
            "payer": gl.message.sender_address.as_hex,
            "beneficiary": beneficiary.as_hex,
            "amount": str(int(amount)),
            "token": "native",
            "deadline": deadline,
            "status": "OPEN",
            "verdict": "",
            "confidence": 0.0,
            "evidence_summary": "",
            "reasoning": "",
            "partial_details": "",
            "appeal_round": 0,
            "revised_checks": "",
        }
        self.escrows[escrow_id] = json.dumps(escrow)
        self.escrow_count = u256(int(self.escrow_count) + 1)
        return escrow_id

    @gl.public.write
    def submit_claim(self, escrow_id: str, claim_text: str, claim_links: str):
        escrow = _load_escrow(self.escrows, escrow_id)
        if gl.message.sender_address.as_hex != escrow["beneficiary"]:
            raise gl.vm.UserError("only the beneficiary can submit a claim")
        if escrow["status"] != "OPEN":
            raise gl.vm.UserError("a claim was already submitted")
        escrow["claim_text"] = claim_text
        escrow["claim_links"] = claim_links
        escrow["status"] = "CLAIMED"
        self.escrows[escrow_id] = json.dumps(escrow)

    @gl.public.write
    def resolve(self, escrow_id: str):
        escrow = _load_escrow(self.escrows, escrow_id)
        if escrow["status"] not in ("CLAIMED", "APPEALED"):
            raise gl.vm.UserError("escrow is not awaiting resolution")

        condition_mem = str(escrow["condition"])
        claim_mem = str(escrow["claim_text"])
        links_mem = str(escrow["claim_links"])
        amount_mem = int(escrow["amount"])
        token_mem = str(escrow["token"])
        payer_mem = str(escrow["payer"])
        beneficiary_mem = str(escrow["beneficiary"])
        deadline_mem = str(escrow["deadline"])
        appeal_round_mem = int(escrow["appeal_round"])
        required_confidence = _required_confidence(amount_mem)
        if amount_mem > HIGH_VALUE_THRESHOLD:
            high_value_note = (
                "HIGH-VALUE ESCROW: only return confidence >= "
                + str(HIGH_VALUE_MIN_CONFIDENCE)
                + " if you have direct on-chain proof of every element."
            )
        else:
            high_value_note = ""

        result = _run_leader_arbitration(
            escrow_id,
            condition_mem,
            claim_mem,
            links_mem,
            amount_mem,
            token_mem,
            payer_mem,
            beneficiary_mem,
            deadline_mem,
            high_value_note,
        )
        if isinstance(result, gl.vm.Return):
            result = result.calldata
        if not isinstance(result, dict):
            raise gl.vm.UserError("arbitration did not produce a verdict")

        verdict = str(result.get("verdict", ""))
        if verdict not in ("RELEASE", "REFUND", "PARTIAL"):
            raise gl.vm.UserError("invalid verdict from arbitration")
        confidence = _to_float(result.get("confidence"))
        evidence_summary = str(result.get("evidence_summary", ""))[:MAX_TEXT_CHARS]
        reasoning = str(result.get("reasoning", ""))[:MAX_TEXT_CHARS]
        partial_details = str(result.get("partial_details", ""))[:MAX_TEXT_CHARS]

        if verdict == "RELEASE" and confidence < required_confidence:
            verdict = "PARTIAL"
            downgrade_note = (
                "Downgraded from RELEASE: confidence "
                + str(confidence)
                + " is below the required threshold "
                + str(required_confidence)
                + " for this escrow value."
            )
            partial_details = (downgrade_note + " " + partial_details).strip()

        escrow["verdict"] = verdict
        escrow["confidence"] = confidence
        escrow["evidence_summary"] = evidence_summary
        escrow["reasoning"] = reasoning
        escrow["partial_details"] = partial_details
        if verdict == "RELEASE":
            escrow["status"] = "RELEASED"
        elif verdict == "REFUND":
            escrow["status"] = "REFUNDED"
        else:
            escrow["status"] = "PARTIAL"

        if escrow["status"] == "RELEASED":
            gl.eth.send(Address(escrow["beneficiary"]), u256(amount_mem))
        elif escrow["status"] == "REFUNDED":
            gl.eth.send(Address(escrow["payer"]), u256(amount_mem))

        self.escrows[escrow_id] = json.dumps(escrow)
        _log_verdict(
            self.verdict_log,
            escrow_id,
            "resolve",
            appeal_round_mem,
            verdict,
            confidence,
            evidence_summary,
            reasoning,
            partial_details,
        )

    @gl.public.write
    def appeal(self, escrow_id: str):
        escrow = _load_escrow(self.escrows, escrow_id)
        if escrow["status"] != "PARTIAL":
            raise gl.vm.UserError("appeal is only available after a PARTIAL verdict")

        condition_mem = str(escrow["condition"])
        details_mem = str(escrow["partial_details"])
        evidence_mem = str(escrow["evidence_summary"])

        def input_fn() -> str:
            return _fill(
                APPEAL_INPUT_TEMPLATE,
                {
                    "condition_text": condition_mem,
                    "partial_details": details_mem,
                    "evidence_summary": evidence_mem,
                },
            )

        raw = gl.eq_principle.prompt_non_comparative(
            input_fn, task=APPEAL_TASK, criteria=APPEAL_CRITERIA
        )
        data = _extract_json(raw)
        if data is None:
            raise gl.vm.UserError("appeal output was not valid JSON")
        revised = str(data.get("revised_condition", "")).strip()
        if not revised:
            raise gl.vm.UserError("appeal output is missing revised_condition")

        escrow["condition"] = revised
        checks = data.get("checks")
        if isinstance(checks, list):
            escrow["revised_checks"] = json.dumps(checks)
        escrow["appeal_round"] = int(escrow["appeal_round"]) + 1
        escrow["status"] = "APPEALED"
        self.escrows[escrow_id] = json.dumps(escrow)
        _log_verdict(
            self.verdict_log,
            escrow_id,
            "appeal",
            escrow["appeal_round"],
            "",
            0.0,
            evidence_mem,
            "condition restated for definitive resolution",
            json.dumps(data, sort_keys=True)[:MAX_TEXT_CHARS],
        )

    @gl.public.view
    def get_escrow(self, escrow_id: str) -> str:
        if escrow_id not in self.escrows:
            raise gl.vm.UserError("escrow not found")
        return self.escrows[escrow_id]

    @gl.public.view
    def get_verdict_log(self) -> str:
        records = []
        for record_json in self.verdict_log:
            records.append(json.loads(record_json))
        return json.dumps(records)
