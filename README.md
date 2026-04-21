# agent-skills-atelier

A personal collection of AI agent skills — built for my own workflows, shared in case they're useful to yours. Compatible with **Claude Code** and **Gemini CLI**.

## Skills

| Skill | Description |
|-------|-------------|
| [brag-refiner](skills/brag-refiner/) | Turn raw work logs and Brag Documents into impact-focused self-advocacy statements. Runs a short interview to surface Why, Impact, and Scope, then outputs polished entries for weekly check-ins or performance reviews. |
| [claude-skills-symlinks](skills/claude-skills-symlinks/) | Create a Git-tracked symlink under `.claude/skills/` pointing to a skill directory elsewhere in the repo. Covers Windows-specific pitfalls (MSYS winsymlinks, Developer Mode, relative paths). |
| [empirical-prompt-tuning](skills/empirical-prompt-tuning/) | Iteratively improve agent prompts (skills, slash commands, CLAUDE.md sections) by having an unbiased executor run them and scoring results from both sides until improvement plateaus. |
| [roundtable](skills/roundtable/) | Convene a panel of domain experts + Devil's Advocate for structured multi-perspective evaluation of proposals, designs, and strategies. |

## Usage

Each skill lives in its own directory under `skills/`. This repository uses a symlink-based architecture to share skills across multiple agent harnesses.

### Registration (Link-once, Sync-all)

To enable a skill, create a relative symbolic link in the `.claude/skills/` directory.

```bash
# Example: Registering the 'roundtable' skill
ln -s ../../skills/roundtable .claude/skills/roundtable
```

- **Claude Code**: Loads skills directly from `.claude/skills/`.
- **Gemini CLI**: Automatically picks up the same skills via a directory-level link (`.gemini/skills -> ../.claude/skills`).

## Notes

These skills are written for my own context and may need adjustment for yours. No guarantees, but PRs and issues are welcome.

## License

MIT
