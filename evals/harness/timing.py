"""usage: timing.py WS "<task> <arm> r<k>" duration_ms"""
import json, pathlib, sys
ws, d, ms = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]); t, a, r = d.split()
p = ws / t / a / f"run-{r[1:]}" / "outputs" / "timing.json"; p.write_text(json.dumps({"duration_ms": ms, "minutes": round(ms / 60000, 1)})); print(p.parent.parent.name, t, a, round(ms/60000,1))
