# tools/selftest — 하네스 셀프테스트 (probe → 비교 왕복)

하네스 배치/환경 변경 후 핵심 메커니즘(chk_dump 양쪽 + compare_probes)이
살아있는지 5분 안에 확인하는 최소 테스트. 2026-07-09 서버에서 검증 완료.

```bash
# 서버의 임의 작업 디렉토리에서 (예: <harness>/_selftest_run) — 삭제 명령 없이 재실행 가능
mkdir -p work/probes_idl && cd work
cp <harness>/tools/idl/chk_dump.pro <harness>/tools/chk_dump.py <harness>/tools/compare_probes.py .
cp <harness>/tools/selftest/smoke_idl.txt <harness>/tools/selftest/smoke_py.py .

# 1) IDL 오라클 probe 생성 (SSW 불필요 — 순수 IDL)
CHK_DIR=$PWD/probes_idl /usr/local/bin/idl < smoke_idl.txt

# 2) Python twin 생성 (정상 + 고의 불일치 2종)
source ~/anaconda3/etc/profile.d/conda.sh && conda activate torchV2
python smoke_py.py

# 3) 비교 — 기대 결과:
python compare_probes.py --oracle probes_idl --py probes_py     --out report_ok   # ALL PASS, exit 0
python compare_probes.py --oracle probes_idl --py probes_py_bad --out report_bad  # DIVERGED, exit 1
#   report_bad: first divergence = b (scalar), m은 iou FAIL + shift_match {axis0:0, axis1:1} 힌트
```

검증 포인트:
- IDL `scope_varname` 자동 변수명 / struct `.sav` 저장 / `/COMPRESS`
- readsav 축 역순 → orientation=logical 정규화 (findgen(3,4) ↔ arange.reshape(4,3).T)
- byte 0/1 배열 자동 iou 지표, float32 스칼라 allclose
- 최초 발산 식별 + 정수 시프트 자동 진단

주의: IDL probe id는 반드시 작은따옴표 (`'01_test'`) — `"01..."`은 8진수로 파싱됨.
