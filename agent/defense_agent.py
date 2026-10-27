"""
defense_agent.py  --  the "blue team" agent loop.  >>> YOU COMPLETE THIS. <<<

Where the attack agent FINDS the bug, the defense agent FIXES it. It works the
same way (the loop, the one-JSON-action-per-turn format, the step limit, the
printing are all written for you). Your job is to fill in the parts marked
`TODO`:
    - Write the SYSTEM PROMPT that explains the job and the JSON format.
    - Add the step where the agent CONFIRMS its own fix.

Its job: read the vulnerable file, rewrite the dangerous SQL using parameterized
queries (the "?" placeholder style already used in seed_database), and WRITE the
corrected code to a NEW file `app_fixed.py`. It must NOT overwrite app.py.

Run this file after you've seen the attack agent find the bug (see the README).
"""

import argparse
import json

from llm import chat
import tools

# How many steps the agent is allowed before we stop it. This is a safety net
# so a confused agent can't loop forever (and burn through your API credits).
MAX_STEPS = 12

# Which folder to work in if the user doesn't pass one on the command line.
# This directory is the HARD BOUNDARY: every tool call is confined to it, so
# the agent can only read and write inside the folder it was given.
DEFAULT_SCAN_DIR = "target_app"


# ---------------------------------------------------------------------------
#  TODO #1 -- THE SYSTEM PROMPT
# ---------------------------------------------------------------------------
# The system prompt is the model's instructions. Write it so the model knows:
#
#   * Its job: it is a security-fix ("blue team") agent. It must read the
#     vulnerable file, produce a corrected version that uses PARAMETERIZED
#     queries (the "?" placeholders already used in seed_database), and write
#     that corrected code to a NEW file named "app_fixed.py". It must NOT
#     overwrite the original app.py.
#   * The tools it can use and when:
#         read_file  -> {"action": "read_file", "path": "<file>"}
#         write_file -> {"action": "write_file", "path": "<file>",
#                        "contents": "<the full corrected file>"}
#         finish     -> {"action": "finish", "answer": "<short summary>"}
#   * The RULES of the conversation:
#         - Reply with EXACTLY ONE JSON object and nothing else (no markdown,
#           no backticks, no explanation around it). Our parser reads one
#           action per turn.
#         - It MUST include this exact sentence (the scan directory is a hard
#           boundary, also enforced in code):
#             "You may only look inside the directory you were given. Do not
#              try to access parent folders or other directories."
#   * TODO #2: before finishing, it must CONFIRM its fix -- read app_fixed.py
#     back and check the dangerous string-concatenation is gone and the queries
#     now use "?" placeholders.
#
# Tip: tell the model to write the ENTIRE corrected file (not just a snippet),
# keeping everything else the same (host 127.0.0.1, port 5000, debug=False) and
# changing ONLY the two vulnerable queries.
SYSTEM_PROMPT = """
TODO: Write the system prompt here. See the notes above for everything it
needs to cover (the job, the tool JSON formats, the one-JSON-per-reply rule,
the hard-boundary sentence, writing to app_fixed.py, and confirming the fix).
"""


def run_tool(action, scan_dir):
    """
    Look at the parsed JSON `action` and run the matching tool.

    `scan_dir` is the directory chosen on the command line. It is passed into
    every file tool as the HARD BOUNDARY, so the model can only ever read or
    write inside it -- even if it asks for ".." or "." or an absolute path.

    Returns a string describing the result, which we hand back to the model.
    This part is DONE -- it simply connects the model's chosen action to the
    real functions in tools.py.
    """
    name = action.get("action")

    if name == "read_file":
        return tools.read_file(scan_dir, action.get("path", ""))

    if name == "write_file":
        return tools.write_file(
            scan_dir,
            action.get("path", ""),
            action.get("contents", ""),
        )

    return "ERROR: unknown action '" + str(name) + "'."


def main(scan_dir):
    # Tell the student which directory this run is working in.
    print("Fixing in: " + scan_dir)

    # The conversation starts with the system prompt, then a first user message
    # that kicks the agent off.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Begin. Read the vulnerable app in the '" + scan_dir + "' "
                "directory, rewrite the unsafe SQL using parameterized queries, "
                "and write the fixed code to app_fixed.py (do not overwrite "
                "app.py). Then confirm your fix."
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
            "Run the defense agent against a directory of the practice app. "
            "The directory is a hard boundary; the agent can only read and "
            "write inside it."
        )
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=DEFAULT_SCAN_DIR,
        help="Folder to work in, relative to the repo root (default: target_app).",
    )
    args = parser.parse_args()
    main(args.directory)
