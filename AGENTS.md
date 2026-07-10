# AGENTS.md

This repository is an execution-verified IDL→Python conversion harness, shipped in two
self-contained language editions:

| Edition | Path | Entry point |
|---|---|---|
| English | `en/` | `en/AGENTS.md` |
| 한국어 (Korean) | `ko/` | `ko/AGENTS.md` |

If you are an agent reading this at the repository root:

1. Determine which edition to use — ask the user, or infer from the conversation language.
2. Treat that edition folder as the working root.
3. Read `<edition>/AGENTS.md` and follow it. It explains how to load the pipeline
   definition under `<edition>/.claude/` (plain markdown: operations contract, role
   definitions, protocol documents) on any agent CLI, with or without native `.claude/`
   support.
