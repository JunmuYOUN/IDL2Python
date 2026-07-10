👋 This is the **IDL → Python conversion + execution-verification (Parity) harness**.

After converting IDL (`.pro`) to Python, it numerically compares the converted Python's outputs — checkpoint by checkpoint — against **the outputs (oracle) produced by actually running the original IDL on the server**, and runs a fix loop until they match.

---

### 📋 Input items

| Item | Description | Example |
|---|---|---|
| **① IDL file** | `.pro` file/directory/Git/web URL | `/path/to/your_routine.pro` |
| **② Conversion purpose** | Why you are converting | `SunPy pipeline integration` |
| **③ Work path** | Output storage directory | `/path/to/work/your_routine_parity/` |
| **④ Validation data method** | How to obtain it | `provide directly` / `request needed spec` / `auto-download` / `search on server` |
| **⑤ Oracle scope** | Scope of IDL-execution comparison | `whole program once` / `per specific function` |

### 💬 Prompt template

```
Convert [IDL file] to Python and validate it against the IDL execution results.

File: [path/URL]
Purpose: [purpose]
Work path: [/save/path]
Validation data: [provide-directly path | request spec | auto-download | search on server]
```

---

### 🔬 Key characteristics

- It does not estimate expected values — it compares against values produced by **actually running IDL**.
- It compares not only the final output but **all intermediate checkpoints**, so when a mismatch occurs it automatically points out
  **which block it first diverged in** (including automatic diagnosis of transpose/pixel-shift/scale).
- Tolerances, array axis orientation, and mask IoU criteria are declared in `policy.yaml`, and the comparator decides mechanically.
- IDL is not re-run in the fix loop (oracle cache).

### ✅ What gets confirmed along the way

1. **G1**: conversion plan + checkpoint plan + comparison policy + data acquisition method
2. **G2**: right before external data download (source/size)
3. **G3**: final result + parity certificate

When you are ready, please fill in the template. 🚀
