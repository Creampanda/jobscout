import json
from jobscout.tools.registry import execute_tool

# happy path
result = execute_tool("search_european_jobs", {"page": 1})
print(result)
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
