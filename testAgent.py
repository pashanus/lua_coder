from typing import TypedDict, Literal, List, Dict
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
import json

from generator import (
    generate_lua_code,
    generate_lua_test,
    fix_lua_with_instruction,
    fix_lua_test_with_instruction,
    generate_output_key,
)
from validator import validate_lua
from plannerAgent import prompt_generate, planner_review

MAX_ITERS = 5


class AgentState(TypedDict, total=False):
    prompt: str
    messages: List[Dict[str, str]]

    status: Literal["running", "waiting_user", "finished", "error"]
    clarification_question: str

    instruction: str
    clean_code: str
    test: str
    final_output: str
    valid: bool
    error: str
    next_node: str
    itrs: int

    code_ok: bool
    test_ok: bool
    busted_ok: bool
    error_history: list


class AgentDecision(BaseModel):
    instruction: str
    next_node: Literal["coder_node", "tester_node", "end"]


def wrap_into_required_format(code: str, key: str) -> str:
    value = f"lua{{{code.strip()}}}lua"
    return json.dumps({key: value}, ensure_ascii=False)


def prompt_generate_node(state: AgentState):
    original_prompt = state["prompt"]

    decision = prompt_generate(original_prompt)

    instruction = decision.get("instruction", "")
    next_node = decision.get("next_node", "ask_user")

    if next_node == "ask_user":
        return {
            **state,
            "status": "waiting_user",
            "clarification_question": instruction,
            "instruction": instruction,
            "next_node": "ask_user",
        }
    full_prompt = f"""{instruction}

INPUT DATA (DO NOT MODIFY):
{original_prompt}
"""

    print("\n=== FINAL PROMPT TO CODER ===\n")
    print(full_prompt)

    return {
        **state,
        "status": "running",
        "instruction": full_prompt,
        "next_node": "coder",
    }


def ask_user_node(state: AgentState):
    return {
        **state,
        "status": "waiting_user",
        "next_node": "ask_user",
    }


def generate_node(state: AgentState):
    code_prompt = state.get("instruction") or state["prompt"]

    code = generate_lua_code(code_prompt)
    test = generate_lua_test(code_prompt, code)

    print("\n=== GENERATED CODE ===\n", code)
    print("\n=== GENERATED TEST ===\n", test)

    return {
        **state,
        "clean_code": code,
        "test": test,
        "valid": False,
        "error": "",
    }


def validate_node(state: AgentState):
    result = validate_lua()

    print("\n=== VALIDATION RESULT ===")
    print("VALID:", result["valid"])
    print("ERROR:", result["error"])

    history = state.get("error_history", [])
    history.append(
        {
            "iteration": state["itrs"],
            "error": result["error"],
            "code_ok": result["code_ok"],
            "test_ok": result["test_ok"],
            "busted_ok": result["busted_ok"],
        }
    )

    return {
        **state,
        "valid": result["valid"],
        "error": result["error"],
        "code_ok": result["code_ok"],
        "test_ok": result["test_ok"],
        "busted_ok": result["busted_ok"],
        "itrs": state["itrs"] + 1,
        "error_history": history[-10:],
    }


def parse_verdict(instruction: str):
    import re

    match = re.search(r"VERDICT:\s*(.*)", instruction)
    if not match:
        return "both"

    verdict = match.group(1).strip().upper()

    if verdict == "CODE BUG":
        return "code"
    if verdict == "TEST BUG":
        return "test"
    if verdict == "BOTH":
        return "both"
    if verdict == "CORRECT":
        return "end"

    return "both"


def review_node(state: AgentState):
    print("\n=== PLANNER REVIEW ===\n")

    if state["valid"] and state["itrs"] > 1:
        print("SKIP REVIEW: already valid")
        return {
            **state,
            "instruction": "VERDICT: CORRECT",
            "next_node": "end",
        }

    planner_result = planner_review(state)
    instruction = planner_result["instruction"]

    print(instruction)

    decision = parse_verdict(instruction)

    return {
        **state,
        "instruction": instruction,
        "next_node": decision,
    }


def fix_node(state: AgentState):
    print("\n=== ERROR SENT TO LLM ===\n")
    print(state["error"])

    planner_result = planner_review(state)
    instruction = planner_result["instruction"]

    print("\n=== PLANNER INSTRUCTIONS ===")
    print(instruction)

    decision = parse_verdict(instruction)

    return {
        **state,
        "instruction": instruction,
        "next_node": decision,
    }


def tester_fix_node(state: AgentState):
    fixed_test = fix_lua_test_with_instruction(
        state["test"],
        state["instruction"],
        state["prompt"],
        state["clean_code"],
    )

    print("\n=== FIXED TEST ===\n")
    print(fixed_test)

    return {
        **state,
        "test": fixed_test,
        "valid": False,
        "error": "",
    }


def coder_fix_node(state: AgentState):
    fixed_code = fix_lua_with_instruction(
        state["clean_code"],
        state["instruction"],
        state["prompt"],
    )

    print("\n=== FIXED CODE ===\n")
    print(fixed_code)

    return {
        **state,
        "clean_code": fixed_code,
        "valid": False,
        "error": "",
    }


def route_after_validate(state: AgentState):
    if state["valid"]:
        return "review"

    if state["itrs"] >= MAX_ITERS:
        return "force_end"

    if not state.get("test_ok", False):
        return "test"

    if not state.get("code_ok", False):
        return "code"

    return "review"


def route_from_prompt(state: AgentState):
    return state.get("next_node", "ask_user")


def final_wrap_node(state: AgentState):
    print("\n=== КОД И JSON ===\n")
    code = state["clean_code"]
    key = generate_output_key(state["prompt"])

    wrapped = wrap_into_required_format(state["clean_code"], key)
    print(code)
    print(wrapped)

    return {
        **state,
        "final_output": state["clean_code"],
        "status": "finished",
        "next_node": "end",
    }


builder = StateGraph(AgentState)

builder.add_node("prompt_generate_node", prompt_generate_node)
builder.add_node("generate_node", generate_node)
builder.add_node("validate_node", validate_node)
builder.add_node("fix_node", fix_node)
builder.add_node("coder_fix_node", coder_fix_node)
builder.add_node("tester_fix_node", tester_fix_node)
builder.add_node("review_node", review_node)
builder.add_node("final_wrap_node", final_wrap_node)
builder.add_node("ask_user_node", ask_user_node)

builder.set_entry_point("prompt_generate_node")

# ВАЖНО: здесь только conditional edges, без прямого add_edge в generate_node
builder.add_conditional_edges(
    "prompt_generate_node",
    route_from_prompt,
    {
        "ask_user": "ask_user_node",
        "coder": "generate_node",
        "end": "final_wrap_node",
    },
)

builder.add_edge("ask_user_node", END)
builder.add_edge("generate_node", "validate_node")

builder.add_conditional_edges(
    "validate_node",
    route_after_validate,
    {
        "code": "coder_fix_node",
        "test": "tester_fix_node",
        "review": "review_node",
        "end": "final_wrap_node",
        "force_end": "final_wrap_node",
    },
)

builder.add_conditional_edges(
    "review_node",
    lambda state: state["next_node"],
    {
        "code": "coder_fix_node",
        "test": "tester_fix_node",
        "both": "coder_fix_node",
        "end": "final_wrap_node",
    },
)

builder.add_conditional_edges(
    "fix_node",
    lambda state: state["next_node"],
    {
        "code": "coder_fix_node",
        "test": "tester_fix_node",
        "both": "coder_fix_node",
        "end": "final_wrap_node",
    },
)

builder.add_edge("coder_fix_node", "validate_node")
builder.add_edge("tester_fix_node", "validate_node")
builder.add_edge("final_wrap_node", END)

graph = builder.compile()