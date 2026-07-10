"""Smoke test: python twin probes + comparator (run on server, torchV2)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from chk_dump import chk_dump  # noqa: E402

# --- twin of the IDL smoke probe (policy orientation = logical) ------------
# IDL: a = findgen(3,4)      -> logical a[i,j] = i + 3*j, shape (3,4)
a = np.arange(12, dtype=np.float32).reshape(4, 3).T          # (3,4), [i,j]=i+3j
# IDL: b = 3.14 (float32)
b = np.float32(3.14)
# IDL: m = bytarr(5,5); m[1:3,2:4]=1b  (inclusive!) -> x 1..3, y 2..4
m = np.zeros((5, 5), dtype=np.uint8)
m[1:4, 2:5] = 1                                              # logical m[x,y]

# run 1: correct twin
os.environ["CHK_DIR"] = os.path.join(HERE, "probes_py")
chk_dump("01_test", a=a, b=b, m=m)

# run 2: intentionally broken twin (scalar off + mask shifted by 1 in y)
os.environ["CHK_DIR"] = os.path.join(HERE, "probes_py_bad")
m_bad = np.roll(m, 1, axis=1)
chk_dump("01_test", a=a, b=np.float32(3.15), m=m_bad)
print("twins written")
