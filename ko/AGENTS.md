# AGENTS.md — 에이전트 CLI 공통 진입점

이 저장소는 IDL(`.pro`)→Python 변환을 **실행 기반 수치 대조(parity)**로 검증하는 에이전트 하네스다.
파이프라인 정의(운영 계약 · 역할 · 프로토콜)는 전부 `.claude/` 아래 **순수 마크다운 문서**이며,
특정 LLM이나 특정 CLI 전용 형식이 아니다.

이 파일은 `.claude/`를 자동 로드하지 않는 에이전트 CLI를 위한 진입점이다:

- **`.claude/`를 네이티브로 로드하는 CLI** (Claude Code 등): 이 파일 없이도 동일하게 동작한다.
  아래 지침은 그런 CLI가 자동으로 수행하는 일을 명시한 것뿐이다.
- **`AGENTS.md`를 읽는 CLI** (OpenAI Codex CLI 등) 또는 그 외 코딩 에이전트: 아래 지침을 따른다.

어느 CLI로 구동하든 파이프라인·규칙·산출물은 동일하다.

## 1. 세션 시작 시 반드시

1. `.claude/CLAUDE.md`를 **전부 읽는다**. 하네스의 운영 계약(파이프라인 8단계, probe 프로토콜,
   수치·좌표 정책, 승인 게이트, 절대 규칙)이 담겨 있으며, 어떤 CLI에서 구동하든 그대로 적용된다.
2. 변환 요청이 들어오면 `.claude/skills/idl2python-orchestrator/skill.md`를 읽고
   그 절차대로 파이프라인을 진행한다.

## 2. 역할 정의 — `.claude/agents/`

5개 역할이 정의되어 있다: `idl-analyzer`, `python-translator`, `parity-runner`,
`test-engineer`, `conversion-reviewer`. 각 파일의 마크다운 본문이 해당 역할의 작업 지침이다.

- **서브에이전트 생성 기능이 있는 CLI**: 각 파일을 해당 서브에이전트의 시스템 프롬프트로 사용한다.
- **단일 에이전트 CLI**: 해당 Phase에 진입할 때 그 역할 파일을 읽고, 그 지침을 채택하여
  **본인이 직접 그 역할로** 수행한다. 역할이 바뀔 때마다 해당 역할 파일을 다시 읽는다.
- 파일 상단의 YAML frontmatter(`name`, `description`)는 메타데이터다. 본문 지침을 따르면 된다.
- 역할별 출력 디렉토리 분리 규칙(`.claude/CLAUDE.md`의 "데이터 전달 규칙")은
  단일 에이전트로 수행할 때도 동일하게 지킨다 — 어느 역할로 작업 중인지에 따라 쓰기 위치가 정해진다.

## 3. 프로토콜 문서 — `.claude/skills/`

각 문서는 정해진 시점에 읽어야 하는 프로토콜/레퍼런스다:

| 문서 | 읽는 시점 |
|---|---|
| `idl2python-orchestrator/skill.md` | 변환 요청 접수 즉시 — 파이프라인 총괄 |
| `parity-protocol/skill.md` | 계측·변환·비교·리뷰 **전에 반드시** — probe 규약, 함정 카탈로그, 발산 진단표 |
| `idl-python-mapping/skill.md` | Python 변환 작업 중 — 구문 매핑 레퍼런스 |
| `data-acquisition/skill.md` | Phase 2 검증 데이터 확보 시 |
| `test-protocol/skill.md` | Phase 6 회귀 테스트 작성 시 |
| `web-source-collector/skill.md` | Phase 0에서 소스가 웹 URL일 때 |

## 4. CLI 기능 차이에 대한 대응

| 하네스 문서가 가정하는 기능 | 그 기능이 없는 CLI에서는 |
|---|---|
| 병렬 실행 (Phase 3 오라클 ∥ Phase 4 변환) | Phase 3 → 4 순차 실행 (결과 동일, 소요 시간만 증가) |
| 서브에이전트 팀 | §2의 단일 에이전트 방식 — 역할 파일을 읽고 직접 수행 |
| 자동 메모리 | 해당 없음 — 이 하네스는 자동 메모리를 사용하지 않는다 (`.claude/CLAUDE.md`의 "Auto-memory policy") |

## 5. CLI와 무관하게 반드시 지킬 것

- **승인 게이트 (G1/G2/G3)**: 채팅으로 사용자에게 질문하고 명시적 승인을 받기 전에는 다음 단계로 진행하지 않는다.
- **삭제 금지**: 셸에서 `rm` 계열 명령을 실행하지 않는다. 생성하는 코드에 `os.remove`,
  `shutil.rmtree` 등 삭제 API를 넣지 않는다 (`.claude/CLAUDE.md`의 "절대 규칙").
- **원본·오라클 불변**: `inbox/`의 원본 `.pro`와 오라클 산출물은 수정하지 않는다.
- **기대값 추정 금지**: 정답은 항상 원본 IDL을 실제로 실행해 얻은 오라클이다.
