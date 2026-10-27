"""
attack_agent.py  --  the agent loop.  >>> THIS IS THE FILE YOU COMPLETE. <<<

The idea of an "agent" is simple:
    1. We give the model a job (the system prompt) and a list of tools it can use.
    2. The model replies with ONE action at a time, written as JSON.
    3. Our code runs that tool and feeds the result back to the model.
    4. Repeat until the model says it's done, or we hit a safety step limit.

The plumbing (the loop, the JSON parsing, the tool dispatch, the printing) is
already written for you below. Your job is to fill in the parts marked
`TODO`:
    - Write the SYSTEM PROMPT that explains the job and the JSON format.
    - Make the agent report the EXACT vulnerable file and line number.
    - Add the step where the agent CONFIRMS the bug against the running app.

Run the target app first (see the README), then run this file.
"""

import argparse
import json

from llm import chat
import tools

# How many steps the agent is allowed before we stop it. This is a safety net
# so a confused agent can't loop forever (and burn through your API credits).
MAX_STEPS = 12

# Which folder to scan if the user doesn't pass one on the command line. This
# is the vulnerable practice app. The value is interpreted by tools.list_files,
# which anchors it to the repo root and refuses anything outside the repo.
DEFAULT_SCAN_DIR = "target_app"


# ---------------------------------------------------------------------------
#  TODO #1 -- THE SYSTEM PROMPT
# ---------------------------------------------------------------------------
# The system prompt is the model's instructions. Write it so the model knows:
#
#   * Its job: it is a security code-scanning agent looking for a SQL injection
#     vulnerability in the practice app's source code.
#   * The tools it can use and when:
#         list_files   -> {"action": "list_files", "root": "<folder>"}
#         read_file    -> {"action": "read_file", "root": "<folder>", "path": "<file>"}
#         send_request -> {"action": "send_request", "method": "GET"|"POST",
#                          "path": "<route>", "data": {<optional json>}}
#         finish       -> {"action": "finish", "answer": "<your final report>"}
#   * The RULES of the conversation:
#         - Reply with EXACTLY ONE JSON object and nothing else (no markdown,
#           no backticks, no explanation around it). Our parser reads one
#           action per turn.
#         - It MUST include this exact sentence (the scan directory is a hard
#           boundary, also enforced in code):
#             "You may only look inside the directory you were given. Do not
#              try to access parent folders or other directories."
#   * TODO #2: it must report the EXACT file and line number of the bug.
#   * TODO #3: before finishing, it must CONFIRM the bug by sending a real
#     request to the local app (e.g. an " ' OR '1'='1 " style login) and
#     checking the response proves the injection worked.
#
# Tip: keep it short and concrete. Show the model one example JSON action.
SYSTEM_PROMPT = """
TODO: Write the system prompt here. See the notes above for everything it
needs to cover (the job, the tool JSON formats, the one-JSON-per-reply rule,
reporting the exact file + line, and confirming the exploit live).
"""


def run_tool(action, scan_dir):
    """
    Look at the parsed JSON `action` and run the matching tool.

    `scan_dir` is the directory chosen on the command line. It is passed into
    every file tool as the HARD BOUNDARY, so the model can only ever read or
    walk inside it -- even if it asks for ".." or "." or an absolute path.

    Returns a string describing the result, which we hand back to the model.
    This part is DONE -- it simply connects the model's chosen action to the
    real functions in tools.py.
    """
    name = action.get("action")

    if name == "list_files":
        # The model may name a sub-folder with "root"; it defaults to "." (the
        # scan directory itself). Either way it stays inside scan_dir.
        files = tools.list_files(scan_dir, action.get("root", "."))
        # list_files returns a list on success, or an error STRING if the path
        # is outside the scan directory. Pass the error through as-is.
        if isinstance(files, str):
            return files
        return "Files found:\n" + "\n".join(files)

    if name == "read_file":
        return tools.read_file(scan_dir, action.get("path", ""))

    if name == "send_request":
        result = tools.send_request(
            action.get("method", "GET"),
            action.get("path", "/"),
            action.get("data"),
        )
        return json.dumps(result)

    return "ERROR: unknown action '" + str(name) + "'."


def main(scan_dir):
    # Tell the student which directory this run is scanning.
    print("Scanning: " + scan_dir)

    # The conversation starts with the system prompt, then a first user message
    # that kicks the agent off.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Begin. Scan the '" + scan_dir + "' directory. Find the SQL "
                "injection vulnerability, report the exact file and line, and "
                "confirm it works."
            ),
        },
    ]

    for step in range(1, MAX_STEPS + 1):
        print("\n" + "=" * 60)
        print("STEP " + str(step))
        print("=" * 60)

        # 1) Ask the model what to do next.
        reply = chat(messages)
        print("Agent says:\n" + reply)

        # Record the model's reply so it remembers its own train of thought.
        messages.append({"role": "assistant", "content": reply})

        # 2) Parse ONE JSON action out of the reply.
        try:
            action = json.loads(reply)
        except json.JSONDecodeError:
            # The model didn't give us clean JSON. Tell it so it can fix itself.
            feedback = (
                "Your last reply was not valid JSON. Reply with exactly one "
                "JSON object describing a single action, and nothing else."
            )
            print("\n[parser] " + feedback)
            messages.append({"role": "user", "content": feedback})
            continue

        # 3) If the model is finished, print its final answer and stop.
        if action.get("action") == "finish":
            print("\n" + "*" * 60)
            print("FINAL REPORT:")
            print(action.get("answer", "(no answer provided)"))
            print("*" * 60)
            return

        # 4) Otherwise run the chosen tool and feed the result back.
        result = run_tool(action, scan_dir)
        print("\nTool result:\n" + result)
        messages.append(
            {"role": "user", "content": "Tool result:\n" + result}
        )

    # If we fall out of the loop, the agent used up all its steps.
    print("\nReached the step limit (" + str(MAX_STEPS) + ") without finishing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Run the attack agent against a directory of the practice app. "
            "The directory is resolved relative to the repo root; anything "
            "outside the repo is refused."
        )
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=DEFAULT_SCAN_DIR,
        help="Folder to scan, relative to the repo root (default: target_app).",
    )
    args = parser.parse_args()
    main(args.directory)
