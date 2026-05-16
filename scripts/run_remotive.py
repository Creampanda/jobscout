import json
from jobscout.tools.registry import execute_tool

# happy path
result = execute_tool("search_remote_jobs", {"limit": 5})
print(f"keys: {list(result.keys())}")
print(f"count: {result.get('count')}")
print(
    f"first job keys: {list(result['jobs'][0].keys()) if result.get('jobs') else 'none'}"
)
print(
    f"snippet sample: {result['jobs'][0]['description_snippet'][:200] if result.get('jobs') else 
'none'}"
)
print(f"json size (limit=5): {len(json.dumps(result))} chars")

# full size — то, что увидит модель в продакшене
full = execute_tool("search_remote_jobs", {})
print(f"json size (default limit=50): {len(json.dumps(full))} chars")

# error path
err = execute_tool("nonexistent_tool", {})
print(f"unknown tool: {err}")
