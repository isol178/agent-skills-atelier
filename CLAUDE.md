# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A collection of Claude Code skills — reusable agent behaviors loaded by Claude Code from `.claude/skills/`. Each skill is a directory containing a `SKILL.md` (YAML frontmatter + markdown body) and optionally `references/` and `scripts/`.

## Adding a new skill

1. Create `skills/<name>/SKILL.md` with the required frontmatter:
   ```yaml
   ---
   name: <name>
   description: >
     <trigger description — this is what Claude uses to decide when to invoke the skill>
   ---
   ```
2. Create a Git-tracked symlink so Claude Code loads it:
   ```
   ln -s ../../skills/<name> .claude/skills/<name>
   ```
3. Add a one-line English description to the README table.

The symlink must use a relative path (`../../skills/<name>`, not an absolute path) so it resolves correctly after cloning.

## Skill structure conventions

- `SKILL.md` body: workflow instructions for the agent. The `description` frontmatter field controls when Claude triggers the skill — keep it precise and use concrete trigger phrases.
- `references/`: supplementary docs the skill body tells the agent to read when needed. Not loaded automatically.
- `scripts/`: helper Python scripts (e.g. score calculation, convergence checking). No package manager or build step required — run directly with `python scripts/<name>.py`.

## Improving a skill's prompt quality

Use the `empirical-prompt-tuning` skill: dispatch a fresh subagent to run the skill against 2–3 scenarios, collect both self-reported feedback (ambiguities, discretionary fills, retries) and measured metrics (success/fail on `[critical]` requirements, accuracy %, step count), then apply one-theme-per-iteration patches until convergence. Never self-review — always dispatch a new subagent.

## Repository conventions

- README skill descriptions: English only.
- Skill SKILL.md body language: match the language of the skill's intended users (current skills are in Japanese).
- No CI, no linter, no test runner at the repo level. Skill validation is done empirically via the tuning workflow above.
