from copy import deepcopy
from typing import Dict, List, Optional

from testAgent import graph


def build_initial_state(prompt: str, messages: Optional[List[Dict[str, str]]] = None):
    return {
        "prompt": prompt,
        "messages": messages or [],
        "status": "running",
        "clarification_question": "",
        "clean_code": "",
        "itrs": 0,
        "instruction": "",
        "test": "",
        "valid": False,
        "error": "",
        "next_node": "",
        "error_history": [],
    }


def prepare_state(
    user_prompt: str,
    messages: Optional[List[Dict[str, str]]] = None,
    state: Optional[dict] = None,
):
    if state is None:
        return build_initial_state(user_prompt, messages)

    new_state = deepcopy(state)

    if messages is not None:
        new_state["messages"] = messages

    if user_prompt:
        prev_prompt = new_state.get("prompt", "")
        if new_state.get("status") == "waiting_user":
            new_state["prompt"] = f"{prev_prompt}\n\n[Ответ пользователя]\n{user_prompt}".strip()
        else:
            new_state["prompt"] = user_prompt

    new_state["status"] = "running"
    new_state["next_node"] = ""

    return new_state


def run_agent(
    user_prompt: str,
    messages: Optional[List[Dict[str, str]]] = None,
    state: Optional[dict] = None,
):
    prepared_state = prepare_state(user_prompt=user_prompt, messages=messages, state=state)
    return graph.invoke(prepared_state)


def run_agent_stream(
    user_prompt: str,
    messages: Optional[List[Dict[str, str]]] = None,
    state: Optional[dict] = None,
):
    prepared_state = prepare_state(user_prompt=user_prompt, messages=messages, state=state)

    for step in graph.stream(prepared_state):
        yield step