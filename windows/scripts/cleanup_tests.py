"""Delete history entries created by automated test scripts (dev helper)."""
import httpx

MARKERS = ["PNG", "png", "銷售", "食譜", "test text", "台南", "春天", "春日",
           "images in a folder"]

items = httpx.get("https://localhost:8443/api/history?archived=all&limit=100",
                  verify=False, timeout=30).json()
deleted = 0
for it in items:
    blob = (it.get("transcript") or "") + (it.get("prompt") or "")
    if any(m in blob for m in MARKERS):
        httpx.delete(f"https://localhost:8443/api/history/{it['id']}",
                     verify=False, timeout=30)
        deleted += 1
print(f"deleted {deleted} test entries; remaining: {len(items) - deleted}")
