import subprocess

def run_luacheck_code():
    result = subprocess.run(
        "luacheck generated/generated.lua --only 0",
        shell=True,
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout + result.stderr


def run_luacheck_test():
    result = subprocess.run(
        "luacheck generated/generated_spec.lua --only 0",
        shell=True,
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout + result.stderr


def run_busted():
    # env = os.environ.copy()
    # env["LUA_INIT"] = "@generated/generated.lua"
    result = subprocess.run(
        "busted generated/generated_spec.lua",
        shell=True,
        capture_output=True,
        text=True
        # env=env
    )
    return result.returncode == 0, result.stdout + result.stderr


def validate_lua():
    code_ok, code_log = run_luacheck_code()
    test_ok, test_log = run_luacheck_test()

    busted_ok = False
    busted_log = ""

    if code_ok and test_ok:
        busted_ok, busted_log = run_busted()

    valid = code_ok and test_ok and busted_ok

    if not code_ok:
        error = f"CODE BUG\nLUACHECK (CODE):\n{code_log}"
    elif not test_ok:
        error = f"TEST BUG\nLUACHECK (TEST):\n{test_log}"
    elif not busted_ok:
        error = f"BUSTED FAILURE\n{busted_log}"
    else:
        error = "SUCCESS!"

    return {
        "valid": valid,
        "code_ok": code_ok,
        "test_ok": test_ok,
        "busted_ok": busted_ok,
        "error": error,
        "code_log": code_log,
        "test_log": test_log,
        "busted_log": busted_log,
    }