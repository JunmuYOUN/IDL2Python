; batch_oracle.pro — headless SSW-IDL oracle batch (TEMPLATE)
;
; parity-runner generates the actual batch from this template by replacing:
;   {{CHK_TOOLS}}   -> absolute path of <harness>/tools/idl  (chk_dump.pro lives here)
;   {{PROBED_PRO}}  -> absolute path of staging/<name>_probed.pro
;   {{CALL}}        -> the entry-point call, e.g.:  solar_seg, temp=getenv('IN_DIR'), outpath=getenv('OUT_DIR')
;
; Environment consumed at run time:
;   CHK_DIR   probe output dir (empty/unset = probes disabled -> baseline run)
;   plus any code-specific vars referenced inside {{CALL}}.
;
; Failure detection contract:
;   IDL batch execution stops on a runtime error and falls back toward the
;   prompt; with stdin </dev/null the process then exits on EOF.
;   => the launcher MUST treat a log without '>>> BATCH done' as FAILURE.
;
print, '>>> BATCH start'
print, '>>> CHK_DIR   = ' + getenv('CHK_DIR')
!path = expand_path('+{{CHK_TOOLS}}') + ':' + !path
.compile {{PROBED_PRO}}
{{CALL}}
print, '>>> BATCH done'
exit
