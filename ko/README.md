# IDL2Python — 실행 검증(Parity) 기반 IDL→Python 변환 하네스

> **English summary** — An agent-CLI harness that converts
> legacy IDL (`.pro`) code to Python and **verifies the conversion by actually running both sides**:
> the original IDL produces *oracle* checkpoints, the converted Python produces *twin* checkpoints,
> and a policy-driven comparator localizes the first divergence and drives a fix loop until
> numerical parity. Built with solar & space-weather research code in mind (SunPy/Astropy ecosystem).

IDL(`.pro`) 코드를 Python으로 변환한 뒤, **원본 IDL과 변환 Python을 실제로 실행해
체크포인트 단위로 수치를 대조(parity check)**하고, 불일치가 사라질 때까지 수정 루프를 도는
자동화 파이프라인이다.

핵심 원칙: **기대값을 추정하지 않는다.** 정답은 항상 원본 IDL을 실제로 실행해 얻은
산출물(오라클)이며, 변환이 끝났다는 판정은 그 오라클과의 수치 일치로만 내려진다.

## 어떻게 검증하는가

양쪽 코드의 의미적으로 같은 지점에 같은 이름의 덤프 호출(twin probe)을 심는다:

```idl
; IDL (계측 사본)                          # Python (변환 코드)
chk_dump, '05_masks', mas, msk             chk_dump('05_masks', mas=mas, msk=msk)
```

- 환경변수 `CHK_DIR`가 없으면 양쪽 다 no-op — 배포 코드에 남아도 무해
- IDL → `probe_05_masks.sav`, Python → `probe_05_masks.npz`
- `tools/compare_probes.py`가 `policy.yaml`(배열 축 방향·허용오차·IoU·라벨 매칭)대로 판정하고
  **최초 발산 지점**과 자동 진단(전치/픽셀 시프트/스케일 의심)을 보고
- 수정 루프에서는 **Python만 재실행** — IDL 오라클은 캐시된다

```
소스 수집 → 분석(+probe 계획+policy 초안) → [승인 G1]
→ 검증 데이터 확보 → IDL 오라클 실행(계측·무결성·캐시) ∥ Python 변환(twin probe)
→ 패리티 루프 [실행→비교→발산 국소화→수정, 기본 최대 5회]
→ 회귀 테스트(pytest) → 품질 검토 → parity certificate
```

## 요구사항

| 요구 | 비고 |
|---|---|
| **IDL 8.x** | 오라클 실행용. 정식/90일 트라이얼 라이선스 모두 가능. 대상 코드가 SolarSoft를 쓰면 SSW 설치 필요 (순수 IDL 코드는 SSW 불필요) |
| **Python 3.10+** | 아래 환경 설정 참조 |
| **에이전트 CLI** | 아무 코딩 에이전트 CLI — `.claude/`를 네이티브로 로드하는 CLI(예: Claude Code)는 그대로, 그 외 CLI(예: OpenAI Codex CLI 등 `AGENTS.md`를 읽는 도구)는 `AGENTS.md`가 진입점. 어느 쪽이든 파이프라인 동일 |
| csh | 헤드리스 IDL 런처용 (Linux 표준) |
| ssh (선택) | IDL이 원격 서버에 있을 때 |
| GPU | **불필요** — 전부 CPU |

## 설치

### 1. 클론

```bash
git clone https://github.com/JunmuYOUN/IDL2Python.git
cd IDL2Python
```

### 2. Python 환경 (conda 권장)

```bash
conda create -n idl2py python=3.10 -y
conda activate idl2py

# 하네스 도구 필수 패키지 (probe 비교기·데이터 확보·회귀 테스트)
pip install numpy scipy astropy pyyaml matplotlib pytest

# 태양·우주기상 연구용 — SSW 루틴 매핑 대상 + 관측 데이터 확보
pip install sunpy aiapy drms scikit-image
```

| 패키지 | 하네스에서의 역할 |
|---|---|
| numpy / scipy | 수치 비교, `scipy.io.readsav`(IDL .sav 읽기), 헝가리안 라벨 매칭 |
| astropy | FITS I/O, WCS, 시간계 — IDL `FITS_READ`/`anytim` 계열의 대응 |
| sunpy | `sunpy.map`, 역서(`sunpy.coordinates.sun`), VSO/Fido 데이터 다운로드 — SSW 루틴의 주 매핑 대상 |
| aiapy / drms | SDO/AIA 보정(`aia_prep` 대응), JSOC 쿼리 |
| pyyaml | `policy.yaml`(비교 정책) 파싱 |
| matplotlib | 발산 diff PNG 생성 |
| scikit-image | 형태학 연산 등 IDL 이미지 처리 루틴의 매핑 대상 |
| pytest | 오라클 고정(oracle-pinned) 회귀 테스트 |

### 3. 환경 프로파일 작성

```bash
cp config/env.template.yaml config/env.yaml   # env.yaml은 gitignore 대상 (호스트/계정은 여기에만)
```

`config/env.yaml`에서 채울 항목:

| 키 | 설명 |
|---|---|
| `exec.mode` | `local`(세션이 IDL 호스트에서 구동) / `ssh`(원격 IDL 호스트를 ssh로 조종) |
| `idl.bin`, `idl.idl_dir` | IDL 실행 파일/설치 경로 |
| `idl.ssw` | SolarSoft 루트 (대상 코드가 SSW를 쓸 때만; 비우면 순수 IDL로 실행) |
| `python.conda_sh`, `python.conda_env` | conda 초기화 스크립트와 위에서 만든 환경 이름 (`idl2py`) |
| `paths.harness_root` | 이 저장소 체크아웃의 절대 경로 |
| `limits.*` | 수정 루프 한도 등 (기본값 사용 가능) |

### 4. 셀프테스트 (~5분, 권장)

probe 생성 → 비교 왕복이 환경에서 동작하는지 확인한다. `tools/selftest/README.md`의 절차대로:

```bash
# 요약: IDL로 probe .sav 생성 → Python twin .npz 생성 → 비교기 실행
# 기대 결과: 정상 twin은 ALL PASS(exit 0), 고의 불일치는 DIVERGED(exit 1) + 시프트 진단
```

## 사용법

이 저장소는 **에이전트 CLI 하네스**다. 파이프라인(분석→오라클→변환→패리티 루프→인증)은
`.claude/`에 정의된 에이전트 팀이 수행하며, 사용자는 승인 게이트에서 개입한다.
파이프라인 정의는 순수 마크다운이라 특정 CLI에 묶이지 않는다.

1. 저장소 루트에서 코딩 에이전트 CLI 세션을 연다:
   ```bash
   cd IDL2Python
   # 에이전트 CLI 세션 시작
   ```
   - `.claude/`를 자동 로드하는 CLI(예: Claude Code): 그대로 시작하면 된다.
   - 그 외 CLI(예: OpenAI Codex CLI): `AGENTS.md`가 진입점이다 — 자동으로 읽지 않는 도구라면
     첫 메시지로 "AGENTS.md를 읽고 따르라"고 지시한다.
2. 변환 요청을 입력한다 (템플릿):
   ```
   [대상.pro]를 Python으로 변환하고 IDL 실행 결과와 대조 검증해줘.

   파일: /path/to/your_routine.pro        (로컬 경로 · Git URL · 웹 URL 모두 가능)
   목적: SunPy 파이프라인 통합
   작업 경로: /path/to/work/your_routine_parity
   검증 데이터: [직접 제공 /path/to/fits | 필요 스펙 요청 | 자동 다운로드(VSO/JSOC)]
   ```
   실제 사용 예시:
   ```
   chimera.pro를 Python으로 변환하고 IDL 실행 결과와 대조 검증해줘.

   파일: /path/to/CHIMERA/repo/chimera.pro
   목적: 코로나홀 검출 파이프라인 Python 통합
   작업 경로: /path/to/work/chimera_parity
   검증 데이터: 서버 내 기존 데이터 탐색 (또는 자동 다운로드)
   ```
3. 진행 중 세 번 확인을 요청받는다:
   - **G1** — 변환 계획 + 체크포인트(probe) 계획 + 비교 정책(`policy.yaml`) 초안.
     최종 산출물의 허용 기준(IoU 등)은 하네스가 **제안**하고 사용자가 수치를 **확정**한다.
   - **G2** — 외부 데이터 다운로드 직전 (출처/용량 고지)
   - **G3** — 최종 결과
4. 완료 시 산출물:
   - `{작업경로}/converted/` — 변환된 Python (+ `requirements.txt`, 변환 로그)
   - `{작업경로}/reports/09_parity_certificate.md` — 환경·입력·정책·판정 전체 기록
   - `{작업경로}/tests/` — 오라클 고정 회귀 테스트 (`pytest tests/ -v`)
   - `{작업경로}/reports/parity/` — probe별 비교 보고서 + 발산 diff PNG

### 검증 데이터의 세 가지 확보 경로

| 경로 | 방식 |
|---|---|
| 직접 제공 | 갖고 있는 FITS 경로를 알려준다 |
| 스펙 요청 | 하네스가 필요한 데이터 명세(계기/파장/시각/레벨)를 표로 제시하고 사용자가 준비 |
| 자동 다운로드 | VSO(인증 불필요) 또는 JSOC(등록 이메일 필요 — 실행 시 질문) — 모든 입력은 manifest+sha256으로 기록 |

### IDL 소스 예시 (SolarSoft)

하네스는 HTML/FTP 디렉터리 인덱스에서 `.pro` 파일을 직접 수집할 수 있다(`web-source-collector` 스킬 참조). 변환 대상을 찾아볼 대표적 SolarSoft 트리:

- 계기·분석 패키지: <https://sohoftp.nascom.nasa.gov/solarsoft/packages/>
- 범용 SSW 유틸리티(`gen`): <https://sohoftp.nascom.nasa.gov/solarsoft/gen/>

## 폴더 구조

```
IDL2Python/
├── README.md / INTRO.md / harness.json
├── AGENTS.md                     # .claude/를 자동 로드하지 않는 에이전트 CLI용 진입점
├── .claude/
│   ├── CLAUDE.md                 # 파이프라인 운영 계약
│   ├── agents/                   # idl-analyzer, python-translator, parity-runner,
│   │                             # test-engineer, conversion-reviewer
│   └── skills/                   # 오케스트레이터, parity 프로토콜, 데이터 확보,
│                                 # IDL↔Python 매핑 레퍼런스 등
├── config/
│   ├── env.template.yaml         # → config/env.yaml 로 복사해 사용 (gitignored)
│   └── policy.template.yaml      # 수치·좌표 비교 정책 템플릿
├── tools/
│   ├── idl/chk_dump.pro          # IDL probe 덤프 (.sav)
│   ├── idl/batch_template.pro    # 헤드리스 오라클 배치 템플릿
│   ├── run_idl_headless.csh      # IDL/SSW-IDL 런처 (SSW 없으면 자동 분기)
│   ├── chk_dump.py               # Python probe 덤프 (.npz, twin)
│   ├── compare_probes.py         # 비교기 — 정책 집행·최초 발산·자동 진단·보고서
│   ├── fetch_data.py             # VSO/JSOC/URL 데이터 확보 + manifest
│   └── selftest/                 # 설치 검증용 셀프테스트
└── _workspace/                   # 작업 공간 구조 안내 (실제 작업은 지정한 경로에 생성)
```

## 태양·우주기상 코드에 특화된 부분

- **SSW → SunPy/Astropy 매핑 레퍼런스** 내장 (`anytim`→`parse_time`, `read_sdo`→`sunpy.map.Map`,
  `aia_prep`→`aiapy.calibrate` 등) — `.claude/skills/idl-python-mapping/`
- **픽셀 좌표·수치 함정 카탈로그**: FITS `CRPIX` 1-based, 리샘플 격자 0.5px 정렬,
  `ROUND`(half-away) vs `np.round`(half-even), `MEDIAN /EVEN`, `SMOOTH` 경계, cubic 커널 차이,
  `STDDEV` ddof, IDL 16-bit 기본 정수 등 — `.claude/skills/parity-protocol/`
- **역서/난수 처리**: `pb0r` 등 SSW 역서와 sunpy 값의 arcsec급 차이, `RANDOMU` 시드 재현 불가
  문제를 오라클 값 주입 방식으로 처리
- **관측 데이터 자동 확보**: `sunpy.net.Fido`(VSO), `drms`(JSOC) 기반 다운로드 + 재현용 manifest

## 안전 규칙 (요약)

- 원본 `.pro`는 절대 수정하지 않는다 (계측은 staging 사본에만)
- 오라클 산출물·캐시는 append-only — 하네스는 어떤 파일도 삭제하지 않는다
- 외부 다운로드, 패키지 설치, 최종 판정 기준은 모두 사용자 승인 후 진행
- JSOC 이메일 등 개인 정보는 하드코딩하지 않는다 (`config/env.yaml`은 gitignore 대상)

## FAQ

**Q. IDL이 없어도 쓸 수 있나?**
아니다. 이 하네스의 존재 이유가 "원본 IDL을 실제로 실행한 산출물과의 대조"이므로
오라클을 만들 IDL 실행 환경(트라이얼 라이선스 가능)이 반드시 필요하다.

**Q. IDL이 원격 서버에만 있다면?**
`config/env.yaml`에서 `exec.mode: ssh` + `exec.host`를 설정하면 모든 IDL/Python 실행이
그 호스트에서 수행된다 (ssh 키 인증 권장).

**Q. 변환만 하고 검증은 생략할 수 있나?**
가능하지만 권장하지 않는다. 검증 없는 변환이 목적이라면 이 하네스의 전신인
구문 변환 파이프라인만으로 충분하다 — 이 하네스의 판정은 항상 실행 대조를 전제로 한다.

**Q. 허용 오차는 누가 정하나?**
중간 체크포인트는 엄격한 기본값(float32 rtol 1e-5, 마스크 IoU 0.999)으로 시작하고,
최종 산출물의 기준은 하네스가 코드 특성을 근거로 제안한 뒤 **G1에서 사용자가 확정**한다.
라이브러리 커널 차이 등 불가피한 불일치는 원인·완화 기준·승인을 갖춘 waiver로만 허용된다.
