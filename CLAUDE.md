# Agent Skills Development Guide

This file provides guidance to AI agents when working with code in this repository.

## What this repo is

A collection of Agent skills — reusable agent behaviors shared across multiple agent harnesses (such as Claude Code and Gemini CLI).

## Repository structure & Sync mechanism

This repository uses a "Link-once, Sync-all" strategy for skill management:

- **Source**: All skill definitions (logic, references, scripts) reside in the `skills/` directory.
- **Claude Code**: Registered on a **per-skill basis** via individual symlinks in `.claude/skills/`.
- **Gemini CLI**: Automatically synchronized via a **directory-level symlink** (`.gemini/skills -> ../.claude/skills`), ensuring any skill added to Claude Code is instantly available to Gemini CLI.

## Adding a new skill

1. Create a new skill directory: `skills/<name>/SKILL.md`.
2. Register the skill to `.claude/skills/` using a relative symlink:
   ```bash
   ln -s ../../skills/<name> .claude/skills/<name>
   ```
3. (Verification) The skill is now automatically visible to Gemini CLI through the `.gemini/skills` directory link. No further action is required.
4. Add a one-line English description to the README table.

**Important**: Always use relative paths for symlinks to ensure they work correctly across different environments.

## Skill structure conventions

- `SKILL.md` body: workflow instructions for the agent. The `description` frontmatter field controls when the agent triggers the skill — keep it precise and use concrete trigger phrases.
- `references/`: supplementary docs the skill body tells the agent to read when needed. Not loaded automatically.
- `scripts/`: helper Python scripts (e.g. score calculation, convergence checking). Run directly with `python scripts/<name>.py`.

## Improving a skill's prompt quality

Use the `empirical-prompt-tuning` skill: dispatch a fresh agent session to run the skill against 2–3 scenarios, collect both self-reported feedback (ambiguities, discretionary fills, retries) and measured metrics (success/fail on `[critical]` requirements, accuracy %, step count), then apply one-theme-per-iteration patches until convergence. Always use an independent evaluator session for review.

## Repository conventions

- README skill descriptions: English only.
- Skill SKILL.md body language: match the language of the skill's intended users (current skills are in Japanese).
- No CI, no linter, no test runner at the repo level. Skill validation is done empirically via the tuning workflow above.
