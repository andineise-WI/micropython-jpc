# Copilot Superpowers - Project Instructions

This project uses the Superpowers agentic development workflow. Follow these instructions for all work in this codebase.

## Core Principles

1. **Brainstorm before coding** — Use the brainstorming skill before any creative work
2. **Plan before implementing** — Use the writing-plans skill to create detailed TDD plans
3. **Test-first always** — No production code without a failing test first (TDD)
4. **Systematic debugging** — Use the 4-phase debugging process for all bugs
5. **Evidence over claims** — Verify before declaring success

## Workflow

For any feature or significant change:
1. Brainstorm → Design spec (saved to `docs/superpowers/specs/`)
2. Plan → Implementation plan (saved to `docs/superpowers/plans/`)
3. Execute → Task-by-task with TDD and two-stage review
4. Finish → Merge/PR with verification

## Skill Usage

Skills in this project activate automatically. When a skill applies to your current task, load and follow it. Skills override default behavior, but user instructions always take precedence.

## Tool Mapping

This project uses VS Code Copilot tools:
- Task tracking: `manage_todo_list`
- Subagent dispatch: `runSubagent`
- File operations: `read_file`, `create_file`, `replace_string_in_file`
- Terminal: `run_in_terminal`
- Search: `grep_search`, `file_search`, `semantic_search`
