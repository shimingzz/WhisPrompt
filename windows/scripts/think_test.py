"""Compare optimization output across think levels (dev helper)."""
import sys
import time

import httpx

text = sys.argv[1] if len(sys.argv) > 1 else "我想要做一個網站可以讓大家上傳食譜然後可以搜尋"

for think in ["off", "low", "high"]:
    t = time.time()
    r = httpx.post("https://localhost:8443/api/text",
                   json={"text": text, "mode": "prompt", "think": think},
                   verify=False, timeout=300)
    d = r.json()
    print(f"=== think={think} ({round(time.time() - t, 1)}s) ===")
    print(d["prompt"])
    print()
