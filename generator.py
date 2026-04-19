import ollama
import re

client = ollama.Client(host="http://localhost:11434")

CODE_PROMPT = """
You are a Lua code generator for a LowCode platform.

Return ONLY valid Lua code.

STRICT RULES:
- Use wf.vars or wf.initVariables for all inputs
- Always return the final result using `return`
- The code must be directly executable (not wrapped in a main function)

IMPORTANT:
- Use {value} to wrap a single value into an array
- Use _utils.array.new() only to create an empty array
- NEVER pass arguments to _utils.array.new()

ALLOWED:
- local helper functions
- loops (for, while)
- conditions (if)

FORBIDDEN:
- function with input parameters like function foo(input)
- custom input variables (input, data, args, etc.)
- wrapping entire logic into a function

CRITICAL:
- Do NOT call any methods on wf (wf.*())
- wf is a data object, not an API
- Only read values from wf (e.g., wf.vars.xxx)

- Only use functions from:
  - standard Lua (string.*, table.*, etc.)
  - _utils.array (new, push)

- Do NOT call any unknown or undefined functions

NO:
- explanations
- markdown
"""

TEST_PROMPT = '''
You are a Lua test generator using Busted.

Return ONLY Lua test code.

RULES:
- Code is a script (not a function)
- Define wf before execution
- Define _utils with array.new() returning {}
- Execute code using:

local result = (function()
    -- CODE
end)()

- Assert result

FORBIDDEN:
- Do NOT call functions from the code
- Do NOT invent input variables

OUTPUT:
describe("test", function()
    it("works", function()

        _utils = {
            array = {
                new = function()
                    return {}
                end
            }
        }

        wf = {
            vars = {
                ...
            }
        }

        local result = (function()
            -- CODE HERE
        end)()

        assert.are.same(expected, result)
    end)
end)
'''

FIX_WITH_INSTRUCTION_PROMPT = """
You are a Lua code fixer for a LowCode platform.

Return ONLY valid Lua code.

CONTEXT:
- The code is a Lua script (NOT a function)
- It uses wf.vars or wf.initVariables
- It must return a value using `return`

RULES:
- Fix ONLY the errors described in INSTRUCTIONS
- Do NOT rewrite everything unless necessary
- Preserve existing logic if correct
- Do NOT introduce new function calls unless they are standard Lua or _utils.array
- Do NOT call methods on wf

IMPORTANT:
- Use {value} to wrap a single value into an array
- Use _utils.array.new() only to create an empty array
- NEVER pass arguments to _utils.array.new()

ALLOWED:
- local helper functions
- loops and conditions

FORBIDDEN:
- function with parameters (function foo(input))
- inventing input variables (input, data, args)
- removing wf usage
- wrapping code into a function

OUTPUT:
Only Lua script
"""

FIX_PROMPT = '''
You are a senior Lua engineer fixing broken code.

Return ONLY fixed Lua code.

STRICT RULES:
- No explanations
- No markdown
- Only Lua code
- Keep original functionality
- Fix ONLY errors reported
'''


def extract_lua_code(text: str) -> str:
    # ищем ```lua ... ```
    match = re.search(r"```(?:lua)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def generate_lua_code(prompt):
    response = client.chat(
        model="qwen2.5-coder:7b",
        messages=[
            {"role": "system", "content": CODE_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )
    raw = response["message"]["content"]
    code = extract_lua_code(raw)
    with open("generated/generated.lua", "w") as f:
        f.write(code)

    return code


def generate_lua_test(prompt, code):
    response = client.chat(
        model="qwen2.5-coder:7b",
        messages=[
            {"role": "system", "content": TEST_PROMPT},
            {"role": "user", "content": f''' 
TASK:
{prompt}
CODE:
{code}
'''
             }
        ]
    )
    raw = response["message"]["content"]
    test = extract_lua_code(raw)
    with open("generated/generated_spec.lua", "w") as f:
        f.write(test)

    return test


def fix_lua_with_instruction(code: str, instruction: str, prompt: str):
    response = client.chat(
        model="qwen2.5-coder:7b",
        messages=[
            {"role": "system", "content": FIX_WITH_INSTRUCTION_PROMPT},
            {"role": "user", "content": f"""
TASK:
{prompt}

CURRENT CODE:
{code}

INSTRUCTIONS:
{instruction}
"""}

        ]
    )

    raw = response["message"]["content"]
    fixed_code = extract_lua_code(raw)

    with open("generated/generated.lua", "w") as f:
        f.write(fixed_code)

    return fixed_code


def fix_lua_test_with_instruction(test: str, instruction: str, prompt: str, code: str):
    response = client.chat(
        model="qwen2.5-coder:7b",
        messages=[
            {"role": "system", "content": TEST_PROMPT},
            {"role": "user", "content": f"""
TASK:
{prompt}

CODE:
{code}

CURRENT TEST:
{test}

INSTRUCTIONS:
{instruction}
"""}
        ]
    )

    raw = response["message"]["content"]
    fixed_test = extract_lua_code(raw)

    with open("generated/generated_spec.lua", "w") as f:
        f.write(fixed_test)

    return fixed_test


def generate_output_key(prompt: str) -> str:
    response = client.chat(
        model="qwen2.5-coder:7b",
        messages=[
            {
                "role": "system",
                "content": "Return ONLY a JSON key name (snake_case or camelCase). No explanation."
            },
            {
                "role": "user",
                "content": f"Task:\n{prompt}\n\nReturn output JSON key:"
            }
        ]
    )
    return response["message"]["content"].strip().replace('"', '')
