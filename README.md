# agent-skills-atelier

A personal collection of Claude agent skills — built for my own workflows, shared in case they're useful to yours.

## Skills

| Skill | Description |
|-------|-------------|
| [claude-skills-symlinks](skills/claude-skills-symlinks/) | Create a Git-tracked symlink under `.claude/skills/` pointing to a skill directory elsewhere in the repo. Covers Windows-specific pitfalls (MSYS winsymlinks, Developer Mode, relative paths). |
| [empirical-prompt-tuning](skills/empirical-prompt-tuning/) | Iteratively improve agent prompts (skills, slash commands, CLAUDE.md sections) by having an unbiased executor run them and scoring results from both sides until improvement plateaus. |
| [roundtable](skills/roundtable/) | Convene a panel of domain experts + Devil's Advocate for structured multi-perspective evaluation of proposals, designs, and strategies. |

## Usage

Each skill lives in its own directory under `skills/`. To use a skill, download the folder and install it via Claude's skill settings.

```
skills/
└── skill-name/
    ├── SKILL.md
    └── ...
```

## Notes

These skills are written for my own context and may need adjustment for yours. No guarantees, but PRs and issues are welcome.

## License

MIT
