"""
tools.py  --  the "hands" the agents use to interact with the world.

This file is COMPLETE. These are the only things the agents are allowed to do:

    list_files(scan_dir, root)            -> list every .py file under a folder
    read_file(scan_dir, path)             -> read a file's contents, with line numbers
    write_file(scan_dir, path, contents)  -> write a file INSIDE the scan directory
    send_request(method, path, data)      -> make an HTTP request to the LOCAL app

The first argument of the file tools, `scan_dir`, is the HARD BOUNDARY the
agent was launched with (from the command line). Every file path is resolved
INSIDE that directory and refused if it escapes -- so even if the model asks
for ".." or "/etc/passwd", it cannot read, walk, or write outside the folder
it was given. As a second safety layer we also confirm the path stays inside
the repo root. The HTTP tool can only ever talk to the practice app on
localhost.
"""

import os

import requests

# The agent is ONLY ever allowed to talk to this exact host. Any attempt to
# reach anywhere else is refused. This keeps your experiments on your own
# machine.
TARGET_HOST = "http://127.0.0.1:5000"

# The repo root: the folder ABOVE this agent/ folder. This file lives at
# <repo>/agent/tools.py, so going up two levels from __file__ gives <repo>.
# This is the SECOND safety layer -- nothing may ever escape the repo.
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Folders we never want to list -- virtual environments, caches, git internals,
# and installed packages. These aren't the project's own code, so skipping them
# keeps the agent focused and its output short.
SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules"}


def _boundary(scan_dir):
    """Return the absolute path of the scan directory (the hard boundary)."""
    return os.path.abspath(os.path.join(BASE, scan_dir))


def _resolve(scan_dir, requested):
    """
    Resolve `requested` INSIDE the scan directory and enforce both boundaries.

    Returns a tuple (target_abspath, error). On success `error` is None. If the
    resolved path escapes the scan directory (primary boundary) or the repo
    root (second safety layer), `target_abspath` is None and `error` is a
    clear message to hand back to the model.
    """
    boundary = _boundary(scan_dir)
    target = os.path.abspath(os.path.join(boundary, requested))

    # Primary boundary: the path must stay inside the scan directory we were
    # given. This is what stops ".." / "." / absolute paths from escaping.
    if os.path.commonpath([boundary, target]) != boundary:
        return None, "ERROR: outside the allowed scan directory"

    # Second safety layer: it must ALSO stay inside the repo root.
    if os.path.commonpath([BASE, target]) != BASE:
        return None, "ERROR: that path is outside the repo. Not allowed."

    return target, None


def list_files(scan_dir, root="."):
    """
    Return a sorted list of all .py files under `root` (searched recursively).

    `root` is resolved INSIDE `scan_dir` (the hard boundary). Anything that
    escapes the scan directory is refused with an error string instead of being
    walked. Paths are returned relative to the scan directory so they are short
    and easy to read, e.g. "app.py".
    """
    target, err = _resolve(scan_dir, root)
    if err:
        return err

    boundary = _boundary(scan_dir)

    # Debug: show exactly which absolute directory we are about to scan, so you
    # can see the agent is staying inside the folder it was given (and not
    # wandering into parent folders, .venv, or other repos).
    print("[list_files] walking: " + target)

    found = []
    for dirpath, dirnames, filenames in os.walk(target):
        # Prune unwanted folders in place so os.walk won't descend into them.
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                full = os.path.join(dirpath, name)
                found.append(os.path.relpath(full, boundary))
    return sorted(found)


def read_file(scan_dir, path):
    """
    Return the contents of a file, with a line number on each line.

    `path` is resolved INSIDE `scan_dir` (the hard boundary). This blocks tricks
    like "../../etc/passwd" or absolute paths that try to escape the folder.
    """
    target, err = _resolve(scan_dir, path)
    if err:
        return err

    if not os.path.isfile(target):
        return "ERROR: no such file: " + path

    with open(target, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    # Number the lines starting at 1 so the agent can report an exact line.
    numbered = []
    for i, line in enumerate(lines, start=1):
        numbered.append(str(i).rjust(4) + ": " + line.rstrip("\n"))
    return "\n".join(numbered)


def write_file(scan_dir, path, contents):
    """
    Write `contents` to a file resolved INSIDE `scan_dir` (the hard boundary).

    Writing is restricted to the scan directory: anything that escapes it (or
    the repo root) is refused. On success it prints the absolute path written
    and returns a short confirmation string.
    """
    target, err = _resolve(scan_dir, path)
    if err:
        return err

    # Make sure the parent folder exists (it will always be inside the
    # boundary, since `target` itself passed the boundary check above).
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(target, "w", encoding="utf-8") as fh:
        fh.write(contents)

    print("[write_file] wrote: " + target)
    return "Wrote " + str(len(contents)) + " characters to " + os.path.relpath(
        target, _boundary(scan_dir)
    )


def send_request(method, path, data=None):
    """
    Make an HTTP request to the LOCAL practice app only.

    method -- "GET" or "POST"
    path   -- the route, e.g. "/login" or "/search?q=mug"
    data   -- a dict sent as JSON on POST requests (ignored for GET)

    Returns a small dict describing the response (status code + body text).
    Refuses anything that is not a GET/POST to TARGET_HOST.
    """
    method = method.upper()
    if method not in ("GET", "POST"):
        return {"error": "only GET and POST are allowed, got: " + method}

    # Make sure the path starts with a slash, then glue it onto our fixed host.
    if not path.startswith("/"):
        path = "/" + path
    url = TARGET_HOST + path

    # Belt-and-suspenders: confirm the final URL really points at our host.
    if not url.startswith(TARGET_HOST):
        return {"error": "refusing to contact anything other than " + TARGET_HOST}

    try:
        if method == "GET":
            resp = requests.get(url, timeout=10)
        else:
            resp = requests.post(url, json=(data or {}), timeout=10)
    except requests.RequestException as exc:
        return {"error": "request failed: " + str(exc)}

    return {"status": resp.status_code, "body": resp.text}
