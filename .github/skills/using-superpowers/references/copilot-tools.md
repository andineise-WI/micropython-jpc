# VS Code Copilot Tool Mapping

Skills use Claude Code tool names. When you encounter these in a skill, use the Copilot equivalent:

| Skill references | Copilot equivalent |
|-----------------|-------------------|
| `Task` tool (dispatch subagent) | `runSubagent` tool |
| Multiple `Task` calls (parallel) | Sequential `runSubagent` calls (Copilot subagents are synchronous) |
| `manage_todo_list` (task tracking) | `manage_todo_list` tool |
| `Skill` tool (invoke a skill) | Skills load automatically via description matching or `/` slash commands |
| `Read` (read files) | `read_file` tool |
| `Write` (create files) | `create_file` tool |
| `Edit` (edit files) | `replace_string_in_file` or `multi_replace_string_in_file` tool |
| `MultiEdit` (batch edits) | `multi_replace_string_in_file` tool |
| `Bash` (run commands) | `run_in_terminal` tool |
| `Grep` (search text) | `grep_search` tool |
| `Glob` (find files) | `file_search` tool |
| `EnterPlanMode` | Not available — use brainstorming skill workflow instead |

## Subagent Support

Copilot supports subagents via `runSubagent`. Unlike Claude Code's `Task` tool:
- Subagents run **synchronously** (you wait for the result)
- Subagents are **stateless** — one prompt in, one response out
- You cannot send follow-up messages to a subagent
- Your prompt must be self-contained with all necessary context

## Skill Discovery

Copilot discovers skills automatically:
1. Skills in `.github/skills/<name>/SKILL.md` (project-level)
2. Skills in `~/.agents/skills/<name>/SKILL.md` (personal)
3. The `description` field in YAML frontmatter drives auto-invocation
4. Skills also appear as `/` slash commands in chat

## Configuration Files

| Claude Code | VS Code Copilot |
|------------|----------------|
| `CLAUDE.md` | `.github/copilot-instructions.md` |
| `GEMINI.md` | N/A |
| `AGENTS.md` | N/A |
| `~/.claude/skills/` | `~/.agents/skills/` |
| `~/.claude/CLAUDE.md` | User-level `.instructions.md` files |
