import os

from gltest.direct import wasi_mock

# Windows quirk: gltest direct loader crashes unlinking its temp stdin file.
_real_unlink = os.unlink


def _quiet_unlink(path, *args, **kwargs):
    try:
        return _real_unlink(path, *args, **kwargs)
    except PermissionError:
        return None


os.unlink = _quiet_unlink

_RESULT_RETURN = b"\x00"
_RESULT_USER_ERROR = b"\x01"

_TEMPLATE_FIELDS = (
    "task",
    "input",
    "leader_answer",
    "validator_answer",
    "output",
    "criteria",
)


def _encode_return(value) -> bytes:
    from genlayer.py import calldata

    return _RESULT_RETURN + calldata.encode(value)


def _encode_error(code: bytes, message: str) -> bytes:
    return code + str(message).encode("utf-8")


def _template_prompt(data) -> str:
    parts = [str(data.get("template", ""))]
    for key in _TEMPLATE_FIELDS:
        if key in data:
            parts.append(str(data[key]))
    return "\n".join(parts)


def _handle_exec_prompt_template(vm, data):
    # Real GenVM renders the template, calls the LLM and post-processes:
    # - EqNonComparativeLeader: 'ok' is the raw LLM answer for the task
    # - EqNonComparativeValidator / EqComparative: 'ok' is a bool decided
    #   by the genvm runtime; direct mode always agrees
    template = str(data.get("template", ""))
    if template in ("EqNonComparativeValidator", "EqComparative"):
        return {"ok": True}
    return wasi_mock._handle_llm_request(vm, {"prompt": _template_prompt(data)})


def _handle_sandbox(vm, data):
    import cloudpickle

    fn = cloudpickle.loads(data.get("data", b""))
    try:
        return _encode_return(fn())
    except Exception as e:
        return _encode_error(_RESULT_USER_ERROR, str(e))


_real_handle_gl_call = wasi_mock._handle_gl_call


def _patched_handle_gl_call(vm, request):
    if isinstance(request, dict):
        if "ExecPromptTemplate" in request:
            return _handle_exec_prompt_template(vm, request["ExecPromptTemplate"])
        if "Sandbox" in request:
            return _handle_sandbox(vm, request["Sandbox"])
    return _real_handle_gl_call(vm, request)


wasi_mock._handle_gl_call = _patched_handle_gl_call
