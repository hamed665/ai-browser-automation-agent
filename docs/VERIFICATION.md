# Verification record

## Baseline

Upstream: browser-use/web-ui at 61962296c38a0d064e0ba02c827192b7a81d1819.
MIT license and source history retained. The original dependency list pins browser-use 0.1.48 and Gradio 5.27.0 alongside older LangChain integrations. The upstream CLI probe failed before startup because python-dotenv was absent in the clean environment. This is an unavailable runtime baseline, not a successful original application run.

A Python 3.12 resolution of the legacy requirements completed. A previous pip-audit of that resolution reported 119 advisory entries in 15 packages: gradio 17; langchain 3; anthropic 1; langchain-community 2; langchain-core 11; langchain-openai 2; langchain-text-splitters 4; langgraph 2; langgraph-checkpoint 6; langgraph-sdk 3; langsmith 5; mcp 10; mem0ai 8; pillow 35; starlette 10. These are advisory entries, not independent exploit demonstrations. The CI job resolves and audits again so changed results stay visible. Migration of that full stack is unfinished.

## Portfolio implementation

Python 3.12.14; uv 0.12.23. New environment isolated with uv.lock.
Local pytest: **9 passed**, including execution of the real controller method body with SDK-boundary doubles. Python compilation of the modified upstream controller passed. Starlette currently emits a TestClient/httpx deprecation warning; no test fails because of it.

The local Chromium download returned a truncated archive in this environment. Therefore local real-browser verification is blocked; the independent GitHub runner installs Chromium and executes the smoke scenario. Do not infer that it passed until its actual Actions result is checked. Screenshot artifacts come from real execution, never generated mockups.

No LLM/provider credentials, production browser profile, customer records or Smart Visions infrastructure were accessed. The controlled fixture is synthetic. No public deployment, real external-site task, arbitrary browsing benchmark, multi-user security audit or full legacy SDK/model integration has been verified.
