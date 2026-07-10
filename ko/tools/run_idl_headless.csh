#!/bin/csh -f
# run_idl_headless.csh — launch a batch .pro under IDL (SSW if configured), headless.
#
# Usage (always with stdin closed and a timeout; caller exports env first):
#   env CHK_DIR=/path/probes/idl CHIM_TEMP=... CHIM_OUT=... \
#     timeout 1800 csh tools/run_idl_headless.csh /abs/path/staging/batch_oracle.pro \
#     < /dev/null >& logs/idl_run_01.log
#
# Env (from config/env.yaml; all optional):
#   IDL_DIR    IDL installation dir (e.g. /usr/local/idl/idl86)
#   IDL_BIN    plain idl executable (default: idl on PATH) — used when no SSW
#   SSW        SolarSoft root — if set and present, runs under SSW-IDL
#   SSW_INSTR  SSW instrument list (default: "aia hmi")
#
# Success contract: the log must contain '>>> BATCH done'. Anything else is a
# failure (license refusal, runtime error, missing files, timeout).

if ($#argv < 1) then
  echo "usage: run_idl_headless.csh <batch.pro>"
  exit 1
endif

setenv IDL_STARTUP $1
if (! $?SSW_INSTR) setenv SSW_INSTR "aia hmi"

set use_ssw = 0
if ($?SSW) then
  if ("$SSW" != "" && -d "$SSW") set use_ssw = 1
endif

if ($use_ssw) then
  # ssw_idl needs IDL_DIR exported (env.yaml idl.idl_dir). Fail fast with a
  # clear message rather than ssw_idl's cryptic "Cannot find idl directory".
  if (! $?IDL_DIR) then
    echo ">>> launcher ERROR: IDL_DIR must be set for SSW-IDL (export it from env.yaml idl.idl_dir)"
    exit 1
  endif
  echo ">>> launcher: SSW-IDL  IDL_DIR=$IDL_DIR SSW=$SSW SSW_INSTR=$SSW_INSTR"
  echo ">>> launcher: IDL_STARTUP=$IDL_STARTUP"
  source $SSW/gen/setup/setup.ssw
  source $SSW/gen/setup/ssw_idl
else
  if (! $?IDL_BIN) set IDL_BIN = idl
  echo ">>> launcher: plain IDL ($IDL_BIN)"
  echo ">>> launcher: IDL_STARTUP=$IDL_STARTUP"
  exec $IDL_BIN
endif
