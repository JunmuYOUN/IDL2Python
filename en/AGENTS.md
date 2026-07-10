# AGENTS.md — Entry Point for Agent CLIs

This repository is an agent harness that verifies IDL (`.pro`) → Python conversion by
**execution-based numerical comparison (parity)**. The pipeline definition (operations
contract · roles · protocols) lives under the `.claude/` directory as **plain markdown
documents** — provider-neutral, not tied to any particular LLM or CLI.

This file tells any coding-agent CLI how to run the harness:

- Some CLIs (e.g., Claude Code) load the `.claude/` directory automatically and follow
  the steps below on their own.
- Any other CLI (e.g., OpenAI Codex CLI, or anything that reads `AGENTS.md`) follows the
  steps below explicitly.

Whichever CLI drives it, the pipeline, rules, and deliverables are identical.

## 1. At session start, always

1. **Read `.claude/CLAUDE.md` in full.** It is the harness's operations contract
   (the 8-phase pipeline, probe protocol, numeric & coordinate policy, approval gates,
   absolute rules) and applies as-is regardless of which CLI you are.
2. When a conversion request comes in, read
   `.claude/skills/idl2python-orchestrator/skill.md` and run the pipeline by its procedure.

## 2. Role definitions — `.claude/agents/`

Five roles are defined: `idl-analyzer`, `python-translator`, `parity-runner`,
`test-engineer`, `conversion-reviewer`. The markdown body of each file is that role's
working instructions.

- **CLIs that can spawn subagents**: use each file as the system prompt of the
  corresponding subagent.
- **Single-agent CLIs**: when entering the corresponding phase, read that role file and
  **perform the role yourself**, adopting its instructions. Re-read the role file each
  time the role changes.
- The YAML frontmatter at the top of each file (`name`, `description`) is metadata;
  follow the body instructions.
- The per-role output-directory separation rules ("Data handoff rules" in
  `.claude/CLAUDE.md`) apply equally when working as a single agent — where you write
  is determined by which role you are currently performing.

## 3. Protocol documents — `.claude/skills/`

Each document is a protocol/reference to be read at a defined moment:

| Document | When to read |
|---|---|
| `idl2python-orchestrator/skill.md` | Immediately upon a conversion request — pipeline coordination |
| `parity-protocol/skill.md` | **Mandatory before** instrumenting, converting, comparing, or reviewing — probe conventions, pitfall catalog, divergence diagnostics |
| `idl-python-mapping/skill.md` | While converting to Python — syntax mapping reference |
| `data-acquisition/skill.md` | During Phase 2 validation-data acquisition |
| `test-protocol/skill.md` | When writing Phase 6 regression tests |
| `web-source-collector/skill.md` | In Phase 0 when the source is a web URL |

## 4. Handling CLI capability differences

| Capability the harness docs assume | On a CLI without it |
|---|---|
| Parallel execution (Phase 3 oracle ∥ Phase 4 conversion) | Run Phase 3 → 4 sequentially (same result, just longer wall time) |
| A subagent team | The single-agent method of §2 — read the role file and perform it yourself |
| Auto-memory | Not applicable — this harness does not use auto-memory ("Auto-memory policy" in `.claude/CLAUDE.md`) |

## 5. Non-negotiable regardless of CLI

- **Approval gates (G1/G2/G3)**: ask the user in chat and do not proceed to the next
  stage without explicit approval.
- **No deletion**: never run `rm`-family shell commands. Never put deletion APIs such as
  `os.remove` or `shutil.rmtree` in generated code ("Absolute rules" in `.claude/CLAUDE.md`).
- **Original & oracle are immutable**: never modify the original `.pro` in `inbox/` or
  the oracle outputs.
- **Never estimate expected values**: the ground truth is always the oracle obtained by
  actually running the original IDL.
