---
name: install-skills
description: Install a new skill for the current session, or permanently into the agent image. Use when asked to "add a skill", "install a skill", "find a skill for X", or "extend capabilities". Triggers on: "install skill", "add skill", "npx skills", "find skill", "skill for X".
---

# Install Skills

## How Skills Are Loaded

Skills are **auto-discovered** — no config changes needed. The runtime scans two locations in priority order:

1. **`workspace/skills/`** — session-level, writable, overrides image skills (same name wins)
2. **`/home/picoclaw/.picoclaw/workspace/skills/`** — baked into the image at build time, always available

Only `name`, `description`, and `path` are injected into the system prompt at startup. The full `SKILL.md` is loaded on demand via `read_file` when the skill is relevant. Supporting files (`references/`, `rules/`, `scripts/`, `assets/`) are accessed by deriving paths from the skill directory.

## Decision: Session-Temporary vs Permanent

**Session-temporary** (default — use this unless asked to make it permanent):

- Write the skill directly into `workspace/skills/<skill-name>/SKILL.md`
- Available immediately, no restart needed
- Lost when the container restarts
- Use for: one-off tasks, trying out a skill, skills specific to a single job

**Permanent (baked into image)**:

- Requires adding the skill to `picoclaw/skills/` on the host and rebuilding the image
- Tell Sebastian: "This skill should be added permanently — copy it to `picoclaw/skills/<name>/` and rebuild the agent image"
- Use for: skills used regularly by this persona

## Installing a Session-Temporary Skill

### From a URL or raw content

Fetch the `SKILL.md` content and write it to the workspace:

```bash
mkdir -p /home/picoclaw/.picoclaw/workspace/skills/<skill-name>
# then write_file the SKILL.md content
```

### From a GitHub repo (npx skills — host machine only)

`npx skills` runs on the **host**, not inside Docker. Instruct Sebastian to run:

```bash
npx skills add <github-org>/<repo>
# e.g. npx skills add vercel-labs/agent-skills
# → interactive picker, clones to temp dir
# → copy chosen skill: cp -r <tmp>/skills/<name> picoclaw/skills/<name>/
# → rebuild image OR copy into running container's workspace/skills/
```

Well-known sources:

- `vercel-labs/agent-skills` — React, React Native, web design, composition patterns
- `Prat011/awesome-llm-skills` — skill-creator, general purpose skills

## Skill File Format

```
skills/
  <skill-name>/
    SKILL.md          # required — frontmatter + instructions
    references/       # docs loaded on demand via read_file
    rules/            # rule files loaded on demand via read_file
    scripts/          # executable scripts run via exec
    assets/           # templates, fonts, files used in output
```

`SKILL.md` frontmatter (required fields):

```markdown
---
name: <skill-name>
description: <when to use this skill — be specific, include trigger phrases>
---
```

## Using Supporting Files

Once you've read a `SKILL.md` and know its path, derive sibling paths:

```
SKILL.md path:    /home/picoclaw/.picoclaw/workspace/skills/my-skill/SKILL.md
Reference file:   /home/picoclaw/.picoclaw/workspace/skills/my-skill/references/api.md
Script:           /home/picoclaw/.picoclaw/workspace/skills/my-skill/scripts/run.py
```

Read references with `read_file`. Execute scripts with `exec`.

## Currently Image-Baked Skills

| Skill                          | Purpose                                       |
| ------------------------------ | --------------------------------------------- |
| `github-agent`                 | GitHub CLI, PRs, commits                      |
| `browser-use`                  | Chromium browser automation                   |
| `vercel-react-best-practices`  | React/Next.js performance patterns (57 rules) |
| `vercel-react-native-skills`   | React Native & Expo patterns                  |
| `vercel-composition-patterns`  | React composition architecture                |
| `vercel-web-design-guidelines` | Web UI/UX review (fetches live guidelines)    |
| `canvas-design`                | Visual art/poster/design output as PNG/PDF    |
| `pdf`                          | Read, create, merge, split, fill, OCR PDFs    |
| `pptx`                         | Create, edit, extract, convert slide decks    |
| `docx`                         | Create, edit, extract Word documents          |
| `install-skills`               | This skill                                    |
| `systematic-debugging`         | Debugging methodology                         |
| `test-driven-development`      | TDD workflow                                  |
