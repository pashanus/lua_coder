import os
import sys

from agent_runner import run_agent


def configure_console():
    # Windows: переключаем консоль в UTF-8
    if os.name == "nt":
        os.system("chcp 65001 > nul")

    # фиксируем кодировки потоков
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")


def read_multiline(prompt: str, submit_token: str = "/send") -> str:
    print("\n" + prompt)
    print(f"Для отправки введи строку {submit_token!r}.")
    print(f"Команды: /exit, /quit, /q")

    lines = []

    while True:
        try:
            line = input()
        except EOFError:
            # На случай, если ввод прервали
            break

        stripped = line.strip()

        if not lines and stripped in {"/exit", "/quit", "/q"}:
            return stripped

        if stripped == submit_token:
            break

        lines.append(line)

    return "\n".join(lines).strip()


def format_result(result: dict) -> str:
    if result.get("status") == "waiting_user":
        question = result.get("clarification_question", "").strip()
        return f"Уточнение от агента:\n{question or '(пустой вопрос)'}"


def main():
    configure_console()

    print("Lua Coder CLI")
    print("Завершение ввода: строка /send.\n")

    state = None
    messages = []

    while True:
        if state and state.get("status") == "waiting_user":
            user_input = read_multiline("Ответ на вопрос агента:")
        else:
            user_input = read_multiline("Опиши задачу или вставь код:")

        if user_input.lower() in {"/exit", "/quit", "/q"}:
            print("Выход.")
            break

        if not user_input:
            print("Пустой ввод, повтори.")
            continue

        messages.append({"role": "user", "content": user_input})

        if state and state.get("status") == "waiting_user":
            result = run_agent(
                user_prompt=user_input,
                messages=messages,
                state=state,
            )
        else:
            result = run_agent(
                user_prompt=user_input,
                messages=messages,
            )

        state = result

        assistant_text = format_result(result)
        print("\n" + "=" * 80)
        print(assistant_text)
        print("=" * 80)

        messages.append({"role": "assistant", "content": assistant_text})

        if result.get("status") == "waiting_user":
            continue


if __name__ == "__main__":
    main()