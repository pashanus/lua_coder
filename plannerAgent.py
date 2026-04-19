import json
import re
import ollama
from typing import Literal
from pydantic import BaseModel

PLANNER_GENERATE_PROMPT = '''
You are a Prompt Optimization Agent.
Your task is to transform user requests into precise, structured prompts for a Lua code generation agent.

- DO NOT write code.
- DO NOT explain your reasoning.
- DO NOT include commentary.

DECISION LOGIC:
1. If the request is too vague, set "next_node" to "ask_user" and write a clarifying question in "instruction".
2. If the request is actionable, set "next_node" to "coder". In this case, "instruction" MUST follow the format below.

Output STRICTLY in this JSON format:
{
  "next_node": "ask_user" | "coder",
  "instruction": "Your question OR the formatted prompt"
}

If status is "coder", the "instruction" field MUST be structured as follows:
TASK:
...
CONSTRAINTS:
...
EDGE CASES:
...

If information is missing but actionable, make reasonable assumptions.
IMPORTANT: The output must be valid JSON. No extra text is allowed.
'''


PLANNER_REVIEW_PROMPT = """
You are a Lua code and test reviewer.

Check if CODE and TESTS match the TASK .

Rules:
- Code wrong → CODE BUG
- Tests wrong → TEST BUG
- Both wrong → BOTH
- Tests pass but logic wrong → BOTH
- Code ok but tests weak → TEST BUG
- All correct → CORRECT


Important:
- "non-empty" = not nil AND not ""
- Wrong logic (AND vs OR) → CODE BUG
- Missing test cases → TEST BUG
- Code must be a Lua script, not a function
- Code must use wf.vars or wf.initVariables
- Code must return a value using `return`
Do NOT write code.

Output EXACTLY:

VERDICT:
CODE BUG / TEST BUG / BOTH / CORRECT

ROOT_CAUSE:
...

EVIDENCE:
...
"""

client = ollama.Client(host="http://localhost:11434")


# генерация промпта для CoderLLM
def prompt_generate(prompt: str) -> dict:
    response = ollama.chat(model="llama3.1:8b", format="json",
                           messages=[
                               {"role": "system", "content": PLANNER_GENERATE_PROMPT},
                               {"role": "user", "content": prompt}
                           ]
                           )

    try:
        content_dict = json.loads(response["message"]["content"])
        return content_dict


    except json.JSONDecodeError:
        # На случай, если модель выдала кривой JSON
        return {
            "next_node": "planner",
            "instruction": "Failed to parse model response",
        }


class AgentDecision(BaseModel):
    instruction: str
    next_node: Literal["coder_node", "tester_node", "end"]

def format_error_history(state: dict) -> str:
    history = state.get("error_history", [])

    if not history:
        return "NONE"

    lines = []
    for h in history[-3:]:  # только последние 3
        lines.append(
            f"[itr {h['iteration']}] "
            f"code_ok={h['code_ok']} "
            f"test_ok={h['test_ok']} "
            f"busted_ok={h['busted_ok']}\n"
            f"{h['error']}\n"
        )

    return "\n---\n".join(lines)

def planner_review(state: dict):
    code = state.get("clean_code", "")
    error = state.get("error", "")
    test = state.get("test", "")
    task = state.get("prompt", "")
    history_text = format_error_history(state)

    user_prompt = f"""
    TASK:
    {task}

    CURRENT ERROR:
    {error}
    
    ERROR HISTORY:
    {history_text}

    CODE:
    {code}

    TESTS:
    {test}

    """

    response = ollama.chat(
        model="llama3.1:8b",
        messages=[
            {"role": "system", "content": PLANNER_REVIEW_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    )

    content = response["message"]["content"].strip()

    return {
        "instruction": content
    }
    







