#!/usr/bin/env python3
"""
Merge the git histories of two or more "anchors" (a doc passage, a code range,
a comment, a function, a whole file, or a string) into one timeline, so you can
see which side moved last, whether it moved alone, and which commits to read.

Usage:
    python trace_divergence.py [options] ANCHOR ANCHOR [ANCHOR ...]

ANCHOR forms (the LABEL= prefix is optional; labels default to A, B, C, ...):
    doc=docs/api.md:120-135        line range at REV          (git log -L)
    code=src/users.py::get_user    function by name at REV    (git log -L :NAME:PATH)
    test=tests/test_users.py       whole file                 (git log --follow)

Options:
    -S, --pickaxe [LABEL=]STRING   commits that changed how often STRING occurs
                                   anywhere in the repo (git log -S); repeatable
    -G, --regex [LABEL=]REGEX      commits whose diff adds or removes a line
                                   matching REGEX (git log -G); repeatable.
                                   Use this for value changes such as
                                   "MAX_RETRIES = 3" -> "MAX_RETRIES = 5",
                                   which -S MAX_RETRIES does not see
    --rev REV                      revision to trace from (default: HEAD)
    --repo PATH                    repository path (default: current directory)
    --mass N                       flag commits touching >= N files (default: 30)
    --limit N                      show only the newest N timeline rows (default: 60)

Line numbers are interpreted against REV, not the working tree. Commits listed
in .git-blame-ignore-revs or touching >= --mass files are shown but not used as
the commit that "wrote" an anchor's current text.
Only the Python standard library and the git CLI are required.

Exit codes:
    0 = timeline printed
    2 = usage error or git failure
"""

from __future__ import annotations

import argparse
import itertools
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REC = "\x1e"
SEP = "\x1f"

# Subjects that usually claim "no behavior change". If such a commit changed
# behavior anyway, the change was probably accidental.
NON_BEHAVIORAL = re.compile(
    r"\b(refactor\w*|format\w*|reformat\w*|lint\w*|prettier|black|isort|ruff|"
    r"style|rename\w*|move[sd]?|cleanup|clean[ -]up|chore|typo\w*|tidy|"
    r"bump|upgrade|migrate to|no[ -]behaviou?r[ -]change|nfc)\b",
    re.IGNORECASE,
)
REVERT = re.compile(r"^revert\b", re.IGNORECASE)
MERGE = re.compile(r"^merge\b", re.IGNORECASE)


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str, stdin: str | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}\n{proc.stderr.strip()}")
    return proc.stdout


@dataclass
class Anchor:
    label: str
    kind: str  # range | func | file | pickaxe | regex
    spec: str  # human-readable form
    path: str | None = None
    start: int | None = None
    end: int | None = None
    func: str | None = None
    needle: str | None = None
    shas: list[str] = field(default_factory=list)  # newest first
    path_aliases: set[str] = field(default_factory=set)


def parse_anchor(raw: str, default_label: str) -> Anchor:
    label, text = default_label, raw
    m = re.match(r"^([A-Za-z][\w.-]*)=(.+)$", raw)
    if m:
        label, text = m.group(1), m.group(2)
    if "::" in text:
        path, _, func = text.rpartition("::")
        return Anchor(label, "func", text, path=path, func=func)
    m = re.match(r"^(.+):(\d+)(?:[-,](\d+))?$", text)
    if m:
        start = int(m.group(2))
        end = int(m.group(3) or start)
        if end < start:
            start, end = end, start
        return Anchor(label, "range", text, path=m.group(1), start=start, end=end)
    return Anchor(label, "file", text, path=text)


def parse_search(raw: str, default_label: str, kind: str) -> Anchor:
    label, needle = default_label, raw
    m = re.match(r"^([A-Za-z][\w.-]*)=(.+)$", raw)
    if m:
        label, needle = m.group(1), m.group(2)
    flag = "-S" if kind == "pickaxe" else "-G"
    return Anchor(label, kind, f"{flag} {needle!r}", needle=needle)


def shas_from(output: str) -> list[str]:
    # -L may print patches even with --no-patch on old git; keep marker lines only.
    return [line[1:].strip() for line in output.split("\n") if line.startswith(REC)]


def collect(repo: Path, rev: str, a: Anchor) -> None:
    fmt = f"--format={REC}%H"
    if a.kind == "range":
        out = git(repo, "log", rev, "-L", f"{a.start},{a.end}:{a.path}", "--no-patch", fmt)
    elif a.kind == "func":
        out = git(repo, "log", rev, "-L", f":{a.func}:{a.path}", "--no-patch", fmt)
    elif a.kind == "file":
        out = git(repo, "log", rev, "--follow", fmt, "--", a.path)
    else:
        out = git(repo, "log", rev, "-S" if a.kind == "pickaxe" else "-G", a.needle, fmt)
    a.shas = list(dict.fromkeys(shas_from(out)))

    if a.path:
        # Every name the file has had, for file-level matching and historical paths.
        out = git(repo, "log", rev, "--follow", "--name-only", fmt, "--", a.path)
        a.path_aliases = {
            line.strip()
            for line in out.split("\n")
            if line.strip() and not line.startswith(REC)
        }
        a.path_aliases.add(a.path)


@dataclass
class Commit:
    sha: str
    ts: int
    date: str
    author: str
    subject: str
    files: list[str]

    @property
    def short(self) -> str:
        return self.sha[:9]


def load_commits(repo: Path, shas: list[str]) -> dict[str, Commit]:
    if not shas:
        return {}
    out = git(
        repo,
        "log",
        "--no-walk=unsorted",
        "--stdin",
        "--name-only",
        f"--format={REC}%H{SEP}%ct{SEP}%as{SEP}%an{SEP}%s",
        stdin="\n".join(shas) + "\n",
    )
    commits: dict[str, Commit] = {}
    for block in out.split(REC)[1:]:
        head, _, rest = block.partition("\n")
        sha, ts, date, author, subject = head.split(SEP, 4)
        files = [f.strip() for f in rest.split("\n") if f.strip()]
        commits[sha] = Commit(sha, int(ts), date, author, subject, files)
    return commits


def chronological(repo: Path, rev: str, commits: dict[str, Commit]) -> list[Commit]:
    """Oldest first by commit date, but never a child before its parent.

    Rebases often give many commits the same timestamp, so sorting by date
    alone can put a commit before the one it was built on.
    """
    if not commits:
        return []
    floor = min(c.ts for c in commits.values()) - 86400
    out = git(repo, "rev-list", "--date-order", "--reverse", f"--max-age={floor}", rev)
    pos = {sha: i for i, sha in enumerate(out.split())}
    return sorted(commits.values(), key=lambda c: (pos.get(c.sha, len(pos)), c.ts))


def ignore_revs(repo: Path) -> set[str]:
    candidates = []
    try:
        configured = git(repo, "config", "--get", "blame.ignoreRevsFile").strip()
        if configured:
            candidates.append(configured)
    except GitError:
        pass
    candidates.append(".git-blame-ignore-revs")
    revs: set[str] = set()
    for name in candidates:
        p = repo / name
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.split("#", 1)[0].strip()
                if re.fullmatch(r"[0-9a-f]{7,40}", line):
                    revs.add(line)
    return revs


def shallow_boundary(repo: Path) -> set[str]:
    p = Path(git(repo, "rev-parse", "--git-path", "shallow").strip())
    if not p.is_absolute():
        p = repo / p
    if not p.is_file():
        return set()
    return {line.strip() for line in p.read_text().split("\n") if line.strip()}


def tags_for(c: Commit, mass: int, ignored: set[str], boundary: set[str]) -> list[str]:
    tags = []
    if c.sha in boundary:
        tags.append("shallow boundary: history before this is missing")
    if MERGE.search(c.subject):
        tags.append("merge")
    if REVERT.search(c.subject):
        tags.append("revert")
    if NON_BEHAVIORAL.search(c.subject):
        tags.append("no-behavior-change?")
    if len(c.files) >= mass:
        tags.append(f"mass:{len(c.files)} files")
    if any(c.sha.startswith(r) for r in ignored):
        tags.append("blame-ignore-revs")
    return tags


def is_sweep(c: Commit, mass: int, ignored: set[str]) -> bool:
    return len(c.files) >= mass or any(c.sha.startswith(r) for r in ignored)


def written_in(a: Anchor, commits: dict[str, Commit], mass: int, ignored: set[str]) -> Commit:
    """Newest commit that changed the anchor's meaning, skipping formatting sweeps."""
    for sha in a.shas:
        if not is_sweep(commits[sha], mass, ignored):
            return commits[sha]
    return commits[a.shas[0]]


def mark(a: Anchor, c: Commit) -> str:
    if c.sha in a.shas:
        return "X"
    if a.kind in ("range", "func") and a.path_aliases & set(c.files):
        return "f"  # touched the anchor's file, but not the anchor itself
    return "."


def path_at(repo: Path, a: Anchor, sha: str) -> str | None:
    for name in [a.path, *sorted(a.path_aliases - {a.path})]:
        try:
            git(repo, "cat-file", "-e", f"{sha}:{name}")
            return name
        except GitError:
            continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        usage="%(prog)s [options] ANCHOR ANCHOR [ANCHOR ...]",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("anchors", nargs="*", metavar="ANCHOR")
    ap.add_argument("-S", "--pickaxe", action="append", default=[], metavar="[LABEL=]STRING")
    ap.add_argument("-G", "--regex", action="append", default=[], metavar="[LABEL=]REGEX")
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--mass", type=int, default=30)
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    labels = (chr(c) for c in range(ord("A"), ord("Z") + 1))
    anchors = [parse_anchor(r, next(labels)) for r in args.anchors]
    searches = [("pickaxe", r) for r in args.pickaxe] + [("regex", r) for r in args.regex]
    anchors += [parse_search(r, f"P{i + 1}", k) for i, (k, r) in enumerate(searches)]
    if len(anchors) < 2:
        ap.error("give at least two anchors (paths and/or -S/-G searches)")
    if len({a.label for a in anchors}) != len(anchors):
        ap.error("anchor labels must be unique")

    repo = Path(args.repo)
    try:
        repo = Path(git(repo, "rev-parse", "--show-toplevel").strip())
        head = git(repo, "rev-parse", "--short", args.rev).strip()
        branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
        shallow = git(repo, "rev-parse", "--is-shallow-repository").strip() == "true"
    except GitError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    warnings: list[str] = []
    if shallow:
        warnings.append(
            "shallow clone: history is truncated, so 'introduced' and 'last co-change' "
            "may be wrong. Run `git fetch --unshallow` if you can."
        )

    for a in anchors:
        if a.path:
            try:
                git(repo, "cat-file", "-e", f"{args.rev}:{a.path}")
            except GitError:
                print(
                    f"error: {a.label}: '{a.path}' does not exist at {args.rev} "
                    "(uncommitted, misspelled, or relative to the wrong directory? "
                    "Paths are relative to the repository root.)",
                    file=sys.stderr,
                )
                return 2
            if git(repo, "status", "--porcelain", "--", a.path).strip():
                warnings.append(
                    f"{a.label}: {a.path} has uncommitted changes; line numbers and "
                    f"function bodies are read from {args.rev}, not the working tree."
                )
        try:
            collect(repo, args.rev, a)
        except GitError as e:
            print(f"error: {a.label} ({a.spec}): {e}", file=sys.stderr)
            return 2
        if not a.shas:
            warnings.append(f"{a.label}: no commits found for {a.spec}.")

    all_shas = list(dict.fromkeys(s for a in anchors for s in a.shas))
    commits = load_commits(repo, all_shas)
    ignored = ignore_revs(repo)
    boundary = shallow_boundary(repo) if shallow else set()
    timeline = chronological(repo, args.rev, commits)

    print(f"Repository : {repo}  ({args.rev} = {head}, branch {branch})")
    print("Anchors    :")
    width = max(len(a.label) for a in anchors)
    for a in anchors:
        if a.shas:
            last = commits[a.shas[0]]
            first = commits[a.shas[-1]]
            meaningful = written_in(a, commits, args.mass, ignored)
            info = f"{len(a.shas)} commits; last changed {last.short} ({last.date})"
            if meaningful is not last:
                info += f", last non-sweep change {meaningful.short} ({meaningful.date})"
            info += f"; history starts {first.short} ({first.date})"
        else:
            info = "no commits"
        print(f"  {a.label:<{width}}  {a.spec}  -- {info}")

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  ! {w}")

    rows = timeline[-args.limit:] if args.limit > 0 else timeline
    print("\nTimeline (oldest -> newest; only commits that changed at least one anchor). "
          "X = changed the anchor, f = changed the anchor's file elsewhere, . = untouched")
    if len(rows) < len(timeline):
        print(f"  ... {len(timeline) - len(rows)} older commits hidden (use --limit 0)")
    cols = "  ".join(f"{a.label:^{max(len(a.label), 1)}}" for a in anchors)
    print(f"  {'date':<10}  {'sha':<9}  {cols}  author / subject")
    for c in rows:
        marks = "  ".join(f"{mark(a, c):^{max(len(a.label), 1)}}" for a in anchors)
        tags = tags_for(c, args.mass, ignored, boundary)
        tag_text = f"  [{', '.join(tags)}]" if tags else ""
        print(f"  {c.date:<10}  {c.short:<9}  {marks}  {c.author}: {c.subject}{tag_text}")

    print("\nPairs:")
    to_read: list[Commit] = []
    pos = {c.sha: i for i, c in enumerate(timeline)}

    def ids(cs: list[Commit]) -> str:
        if not cs:
            return "(none)"
        more = f" (+{len(cs) - 8} older)" if len(cs) > 8 else ""
        return ", ".join(c.short for c in cs[-8:]) + more

    for x, y in itertools.combinations(anchors, 2):
        if not x.shas or not y.shas:
            continue
        both = [c for c in timeline if c.sha in x.shas and c.sha in y.shas]
        if both:
            start_at = both[-1]
            print(f"  {x.label} <-> {y.label}: last changed together in "
                  f"{start_at.short} ({start_at.date}) {start_at.subject}")
            label = "since then"
        else:
            # Never changed together: the divergence can only start once both exist.
            fx, fy = commits[x.shas[-1]], commits[y.shas[-1]]
            older, newer = (x, y) if pos[fx.sha] <= pos[fy.sha] else (y, x)
            start_at = commits[newer.shas[-1]]
            print(f"  {x.label} <-> {y.label}: never changed together; {older.label} existed first, "
                  f"{newer.label} appeared in {start_at.short} ({start_at.date}) {start_at.subject}")
            if not is_sweep(start_at, args.mass, ignored):
                to_read.append(start_at)
            label = f"since {newer.label} appeared"
        after = timeline[pos[start_at.sha] + 1:]
        for side, other in ((x, y), (y, x)):
            alone = [c for c in after if c.sha in side.shas and c.sha not in other.shas]
            print(f"    only {side.label} moved {label}: {ids(alone)}")
            to_read.extend(c for c in alone if not is_sweep(c, args.mass, ignored))

    print("\nTrue-when-written checks (each anchor's current text vs. the others "
          "as they were when that text was written):")
    any_check = False
    for a in anchors:
        if not a.shas or not a.path:
            continue
        written = written_in(a, commits, args.mass, ignored)
        targets: dict[str, list[str]] = {}
        missing: list[str] = []
        for b in anchors:
            if b is a or not b.path:
                continue
            name = path_at(repo, b, written.sha)
            if name:
                targets.setdefault(name, []).append(b.label)
            else:
                missing.append(b.label)
        if not targets and not missing:
            continue
        any_check = True
        print(f"  {a.label} written in {written.short} ({written.date}):")
        for name, labels in targets.items():
            print(f"    {', '.join(labels)}: git show {written.short}:{name}")
        if missing:
            print(f"    {', '.join(missing)}: did not exist yet")
    if not any_check:
        print("  (needs at least two path anchors)")

    if to_read:
        uniq = sorted({c.sha: c for c in to_read}.values(), key=lambda c: pos[c.sha])[-6:]
        print("\nRead first (where the divergence can have started, oldest -> newest; "
              "formatting sweeps omitted):")
        for c in uniq:
            print(f"  git show {c.short}    # {c.date} {c.author}: {c.subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
