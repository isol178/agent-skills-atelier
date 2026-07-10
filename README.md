# agent-skills-atelier

A personal collection of AI agent skills — built for my own workflows, shared in case they're useful to yours. Compatible with **Claude Code**, **Antigravity CLI**, and **Codex CLI**.

## Skills

| Skill | Description |
|-------|-------------|
| [adr](skills/adr/) | Capture the *why* behind non-trivial technical decisions as MADR 4.0.0 Architecture Decision Records — detects decision signals (S1–S6), guides drafting with context/alternatives/trade-offs, and validates each ADR before commit. |
| [azure-devops-pr](skills/azure-devops-pr/) | Operate Azure DevOps Pull Requests via `az repos pr` and REST API — create, list, inspect, comment/thread, add reviewers, vote, link Work Items, and update PR metadata. |
| [brag-refiner](skills/brag-refiner/) | Turn raw work logs and Brag Documents into impact-focused self-advocacy statements. Runs a short interview to surface Why, Impact, and Scope, then outputs polished entries for weekly check-ins or performance reviews. |
| [claude-skills-symlinks](skills/claude-skills-symlinks/) | Create a Git-tracked symlink under `.claude/skills/` pointing to a skill directory elsewhere in the repo. Covers Windows-specific pitfalls (MSYS winsymlinks, Developer Mode, relative paths). |
| [delegated-task-protocol](skills/delegated-task-protocol/) | Work protocol for a subagent executing a delegated task (implementation/test/fix) — stay within assigned files, never invent unverified names (functions, columns, endpoints), run verification commands before declaring done, report results in a fixed format, and stop on ambiguous contracts. |
| [deliberate](skills/deliberate/) | Pre-coding decision framework for design, tech-selection, and spec-direction questions. Writes no code; structures the discussion by reversibility, decision drivers, and reversal conditions, then routes the decision to an ADR and the implementation to implementation-planning. |
| [empirical-prompt-tuning](skills/empirical-prompt-tuning/) | Iteratively improve agent prompts (skills, slash commands, CLAUDE.md sections) by having an unbiased executor run them and scoring results from both sides until improvement plateaus. |
| [implementation-planning](skills/implementation-planning/) | Planning framework for substantial implementation (3+ files or cross-layer frontend/backend/docs changes) — reconcile against canonical docs, run a premortem of known traps, decompose into sequential/parallel tasks, and predefine completion criteria before writing code. Includes full/light plan-document templates in `references/` for when the plan needs to persist across sessions or delegation. |
| [maintaining-docs-for-jit-loading](skills/maintaining-docs-for-jit-loading/) | Split large Markdown documents into per-section files with an INDEX.md for JIT (Just-In-Time) loading, or merge them back for review or LLM input. |
| [pattern-anchoring](skills/pattern-anchoring/) | Before creating new files (component, route, model, repository, test…), identify the 2–3 nearest existing files as anchors and follow this codebase's own structure and idioms instead of generic training-data patterns, reporting which files were referenced. |
| [roundtable](skills/roundtable/) | Convene a panel of domain experts + Devil's Advocate for structured multi-perspective evaluation of proposals, designs, and strategies. |
| [systematic-debugging](skills/systematic-debugging/) | Thinking protocol for non-obvious bugs — check known traps, separate observation from speculation, maintain a hypothesis ledger, run minimal discriminating experiments, and bisect by layer, instead of shotgun debugging. |

## Usage

Each skill lives in its own directory under `skills/`. This repository uses a symlink-based architecture to share skills across multiple agent harnesses.

### Registration (Link-once, Sync-all)

To enable a skill, create a relative symbolic link in the `.claude/skills/` directory.

```bash
# Example: Registering the 'roundtable' skill
ln -s ../../skills/roundtable .claude/skills/roundtable
```

- **Claude Code**: Loads skills directly from `.claude/skills/`.
- **Antigravity CLI**: Automatically picks up the same skills via a directory-level link (`.agents/skills -> ../.claude/skills`).
- **Codex CLI**: Automatically picks up the same skills via a directory-level link (`.agents/skills -> ../.claude/skills`).

## Notes

These skills are written for my own context and may need adjustment for yours. No guarantees, but PRs and issues are welcome.

## License

MIT
