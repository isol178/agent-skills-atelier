---
name: claude-skills-symlink
description: Create a Git-tracked symlink under `.claude/skills/` pointing to a skill directory elsewhere in the repo, so Claude Code loads the skill while Git records only the symlink (not duplicate files). Use whenever the user wants to expose a skill to Claude Code via a symlink, share skills across a repo, or reports that their symlink is being tracked as duplicate files by Git. Focused on the Windows-specific Git Bash pitfalls (MSYS winsymlinks, Developer Mode, relative paths) that cause `ln -s` to silently copy directories instead of linking. Also use when the user mentions `mklink`, `core.symlinks`, "symlink not working in Git", or "skill appears twice in Claude Code".
---

# Claude Skills Symlink

Expose a skill to Claude Code by placing a Git-tracked symlink at `.claude/skills/<skill-name>` that points to the real skill directory elsewhere in the repo.

## When this matters

Claude Code loads skills from `.claude/skills/`. But the actual skill source often lives elsewhere (e.g. `skills/data/<name>/`, shared across multiple locations, or organized by domain). A symlink bridges the two without duplicating files.

If done wrong, Git tracks the symlink's target directory contents as duplicate files. If done right, Git records just the symlink as a single `120000`-mode entry and the target's files are tracked only once at their real location.

## The golden path

**Use Git Bash. Use `ln -s`. Use a relative path. Set `MSYS=winsymlinks:nativestrict` on Windows.**

That's it. The rest of this document explains why each piece matters, how to prepare Windows once, and how to verify.

## Prerequisites

- **Git Bash** (Windows) or any POSIX shell (macOS / Linux / WSL)
- **Windows only**: Developer Mode enabled (see next section)
- **Windows only**: `git config core.symlinks true` in the target repo (or set globally: `git config --global core.symlinks true`)

## Windows one-time setup: Developer Mode

Native symlinks on Windows require either admin privileges **or** Developer Mode. Developer Mode is the right answer for day-to-day use — enable it once and `ln -s` works from a normal shell forever after.

### Check whether it's already on

In PowerShell:

```powershell
Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" -Name AllowDevelopmentWithoutDevLicense -ErrorAction SilentlyContinue
```

If it prints `AllowDevelopmentWithoutDevLicense : 1`, you're set. If it prints `0` or nothing, enable it.

### Enable it

GUI path: Settings → Privacy & security → For developers → Developer Mode → On.

Or via PowerShell (administrator):

```powershell
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" /t REG_DWORD /f /v "AllowDevelopmentWithoutDevLicense" /d "1"
```

No reboot needed. After this, `ln -s` in Git Bash with `MSYS=winsymlinks:nativestrict` will succeed without elevation.

## Procedure

From the repo root, in Git Bash (Windows) or a regular shell (macOS/Linux):

```bash
# Windows only — force native symlinks, fail loudly if they can't be made.
# Harmless no-op on macOS/Linux, so safe to always include in docs.
export MSYS=winsymlinks:nativestrict

# Create the symlink with a RELATIVE path, from inside the link's parent directory
cd .claude/skills
ln -s ../../<path-to-skill-source> <skill-name>
cd -

# Verify it's actually a symlink (first char `l`, and `->` shows the target)
ls -la .claude/skills/<skill-name>

# Verify Git sees it as a symlink (mode should be 120000, NOT 040000 or 100644)
git add .claude/skills/<skill-name>
git ls-files -s .claude/skills/<skill-name>
```

### Example

Skill source at `skills/data/gcs-operator/`, link at `.claude/skills/gcs-operator`:

```bash
export MSYS=winsymlinks:nativestrict
cd .claude/skills
ln -s ../../skills/data/gcs-operator gcs-operator
cd -
ls -la .claude/skills/gcs-operator
# expected: lrwxrwxrwx ... .claude/skills/gcs-operator -> ../../skills/data/gcs-operator
git add .claude/skills/gcs-operator
git ls-files -s .claude/skills/gcs-operator
# expected: 120000 <hash> 0       .claude/skills/gcs-operator
```

### One-liner variant (required when shell state isn't preserved between commands)

Some automated environments start a fresh shell for every command, so `export` set in one step doesn't survive into the next. **Claude Code's Bash tool always starts a fresh shell per invocation** — so when this skill is executed by a Claude Code agent, always use the one-liner form. Pass the env var inline and chain the commands into a single invocation:

```bash
MSYS=winsymlinks:nativestrict bash -c 'cd .claude/skills && ln -s ../../<path-to-skill-source> <skill-name>'
```

Verification (`ls -la` and `git ls-files -s`) can be run as independent commands afterwards — they don't need the env var.

For interactive use in Git Bash, the multi-line form above is fine and easier to read. The one-liner is only needed when shell state isn't preserved.

## Why each step matters

### Why `ln -s` and not `mklink /D`?

`mklink /D` creates a valid OS-level symlink, but **Git for Windows records it as a regular directory** and tracks every file inside as a new entry. `ln -s` from Git Bash (with `MSYS=winsymlinks:nativestrict`) produces a symlink Git records as mode `120000` — a single file containing the link's target path. No duplicate tracking.

### Why `MSYS=winsymlinks:nativestrict`?

Git Bash's default `ln -s` behavior on Windows is inconsistent. Depending on environment and version it may silently **copy the target directory** instead of linking. Then `ls -la` shows `drwxr-xr-x` instead of `lrwxrwxrwx`, and Git tracks every file as new.

The options:

- unset or `winsymlinks:lnk` — may produce a Windows `.lnk` shortcut (useless for Git)
- `winsymlinks:native` — makes a native symlink if possible, **silently falls back to copy** if not. Avoid.
- `winsymlinks:nativestrict` — makes a native symlink, **fails loudly** if it can't (e.g. Developer Mode off). Use this.

On macOS/Linux/WSL, `ln -s` just works and `MSYS` is ignored.

### Why a relative path, not absolute?

Absolute paths like `C:\Users\yourname\project\skills\data\gcs-operator` break the moment anyone else clones the repo, you move the project, or you switch between Windows and WSL. Relative paths like `../../skills/data/gcs-operator` work everywhere as long as the repo layout is preserved.

### Why create the link from inside the link's parent directory?

`ln -s` stores the target path **verbatim**, and the stored path is later resolved **relative to where the link file lives**. If you `cd` into the link's directory first, the path you type is exactly what gets stored, and the mental model matches reality. (It also works from the repo root, but you have to type a path that looks wrong — it has to be relative to the future link's location, not your current directory.)

### Why `core.symlinks=true`?

Git on Windows sometimes defaults `core.symlinks` to `false`, which causes cloned symlinks to materialize as plain text files containing the target path. Setting it to `true` tells Git to materialize them as real symlinks on checkout.

## Verification checklist

After creating a symlink, confirm all three:

| Check | Command | Expected |
|---|---|---|
| OS sees a symlink | `ls -la .claude/skills/<name>` | line starts with `l`, shows `-> <target>` |
| Git sees a symlink | `git ls-files -s .claude/skills/<name>` | mode `120000` |
| Git status is clean | `git status` | the link appears as a single entry, NOT as a directory with many files inside |

If any fail, see troubleshooting.

## Troubleshooting

### `ls -la` shows `drwxr-xr-x` instead of `lrwxrwxrwx`

The link was created as a directory copy, not a symlink. Common causes:

- `MSYS=winsymlinks:nativestrict` was not set before `ln -s`
- Developer Mode is off on Windows
- An earlier attempt (e.g. `mklink /D` or a failed `ln -s`) left a real directory at the link path, and the new `ln -s` refused to overwrite it

Fix — remove the bogus entry and retry:

```bash
rm -rf .claude/skills/<skill-name>
export MSYS=winsymlinks:nativestrict
cd .claude/skills
ln -s ../../<path-to-skill-source> <skill-name>
cd -
```

### `ln -s` errors with "Operation not permitted" on Windows

Developer Mode is off. See the "Windows one-time setup" section above. No admin/elevated shell needed after enabling it.

### `git ls-files -s` shows mode `040000` or `100644`

OS made a real symlink but Git isn't recording it as one. Usually `core.symlinks=false`. Fix:

```bash
git config core.symlinks true
git rm --cached .claude/skills/<skill-name>
git add .claude/skills/<skill-name>
```

### `git status` shows the linked directory's individual files as untracked

Same root cause as above — Git is treating the link as a directory. Check:

1. Is it a symlink at the OS level? (`ls -la` → starts with `l`)
2. Is `core.symlinks=true`?

### The link works locally but a teammate's clone shows it as a plain text file

They need `git config core.symlinks true` (ideally globally) **before cloning**, or they need to re-checkout after setting it:

```bash
git checkout -- .claude/skills/<skill-name>
```

Windows teammates also need Developer Mode on.

## Persisting the environment variable

If you create symlinks often on Windows, add the export to Git Bash's startup so you don't have to remember it every session:

```bash
echo 'export MSYS=winsymlinks:nativestrict' >> ~/.bashrc
```

## Summary

Four rules:

1. `ln -s` in Git Bash — never `mklink /D`
2. `MSYS=winsymlinks:nativestrict` on Windows (Developer Mode enabled once as prerequisite)
3. Relative path, created from inside the link's parent directory
4. Verify with `ls -la` (`l...`) **and** `git ls-files -s` (mode `120000`)

If all four hold, Git tracks one symlink entry instead of duplicating every file in the target.