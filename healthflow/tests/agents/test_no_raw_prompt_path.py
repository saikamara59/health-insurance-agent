"""Static guarantee: no agent calls _build_prompt with raw arguments.

Every _build_prompt call site must receive exactly one argument, and that
argument must be a Name (a variable holding a PromptInput) — never a literal,
never multiple positional args. This locks in the typed-layer contract: the
only way to reach a prompt body is through a PromptInput constructor.

If this test ever proves noisy on a legitimate dynamic call pattern, it can
be removed — the type annotation on each _build_prompt is the primary
enforcement; this is belt-and-suspenders.
"""
import ast
from pathlib import Path

import pytest

_AGENT_DIR = Path(__file__).resolve().parent.parent.parent / "agents"
_AGENT_FILES = [
    "comparison_agent.py",
    "cost_calculator_agent.py",
    "network_agent.py",
    "translation_agent.py",
    "appeal_agent.py",
]


@pytest.mark.parametrize("filename", _AGENT_FILES)
def test_build_prompt_called_only_with_a_single_variable(filename):
    source = (_AGENT_DIR / filename).read_text()
    tree = ast.parse(source, filename=filename)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match calls of the form `self._build_prompt(...)` or `<obj>._build_prompt(...)`.
        if not (isinstance(func, ast.Attribute) and func.attr == "_build_prompt"):
            continue
        # Exactly one positional arg, no keyword args.
        if len(node.args) != 1 or node.keywords:
            offenders.append((node.lineno, "must take exactly one positional arg"))
            continue
        arg = node.args[0]
        # The single arg must be a Name (a variable), not a literal/list/dict/call-chain.
        if not isinstance(arg, ast.Name):
            offenders.append((node.lineno, f"arg is {type(arg).__name__}, expected Name"))

    assert not offenders, (
        f"{filename}: _build_prompt called with raw arguments: {offenders}. "
        f"Construct a PromptInput and pass that variable instead."
    )
