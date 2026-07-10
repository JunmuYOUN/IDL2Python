;+
; chk_dump — parity probe dumper (IDL side). Twin: tools/chk_dump.py
;
; Usage (insert only at statement boundaries in the instrumented copy):
;   chk_dump, '05_ratio_masks', mas, msk, mak
;   chk_dump, '03_thr', t171, t193, names=['t171','t193']   ; names for expressions
;
; Behavior:
;   - No-op when env CHK_DIR is empty  -> safe to leave calls in shipped code.
;   - Saves struct CHK (fields = caller variable names via SCOPE_VARNAME,
;     fallback names= keyword, fallback v<k>) to $CHK_DIR/probe_<id>.sav
;     with /COMPRESS.
;   - Undefined variables are skipped with a warning (run continues).
;   - Never modifies its arguments. Never deletes anything.
;
; Note: scipy.io.readsav returns these arrays with DIMENSIONS REVERSED
;       (IDL fltarr(nx,ny) -> numpy shape (ny,nx)). The comparator
;       (tools/compare_probes.py) normalizes per the policy 'orientation'.
;-
pro chk_dump, id, v1, v2, v3, v4, v5, v6, v7, v8, names=names
  compile_opt idl2
  on_error, 2

  dir = getenv('CHK_DIR')
  if dir eq '' then return
  nv = n_params() - 1
  if nv le 0 then return

  chk = create_struct('probe_id', string(id))

  for k = 0, nv-1 do begin
    def = 0b
    nm = ''
    case k of
      0: begin
           def = n_elements(v1) gt 0
           nm = scope_varname(v1, level=-1)
           if def then val = v1
         end
      1: begin
           def = n_elements(v2) gt 0
           nm = scope_varname(v2, level=-1)
           if def then val = v2
         end
      2: begin
           def = n_elements(v3) gt 0
           nm = scope_varname(v3, level=-1)
           if def then val = v3
         end
      3: begin
           def = n_elements(v4) gt 0
           nm = scope_varname(v4, level=-1)
           if def then val = v4
         end
      4: begin
           def = n_elements(v5) gt 0
           nm = scope_varname(v5, level=-1)
           if def then val = v5
         end
      5: begin
           def = n_elements(v6) gt 0
           nm = scope_varname(v6, level=-1)
           if def then val = v6
         end
      6: begin
           def = n_elements(v7) gt 0
           nm = scope_varname(v7, level=-1)
           if def then val = v7
         end
      7: begin
           def = n_elements(v8) gt 0
           nm = scope_varname(v8, level=-1)
           if def then val = v8
         end
      else:
    endcase

    if n_elements(names) gt k then begin
      if names[k] ne '' then nm = names[k]
    endif
    if nm eq '' then nm = 'v' + strtrim(k, 2)

    if ~def then begin
      print, 'chk_dump: [' + string(id) + '] skip undefined var: ' + nm
      continue
    endif

    chk = create_struct(chk, idl_validname(nm, /convert_all), val)
  endfor

  file = dir + path_sep() + 'probe_' + string(id) + '.sav'
  save, chk, filename=file, /compress
  print, 'chk_dump: wrote ' + file
end
