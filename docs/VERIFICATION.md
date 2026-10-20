# Verification record

## Baseline

Upstream: browser-use/web-ui at 61962296c38a0d064e0ba02c827192b7a81d1819.
MIT license and source history retained. The original dependency list pins browser-use 0.1.48 and Gradio 5.27.0 alongside older LangChain integrations. The upstream CLI probe failed before startup because python-dotenv was absent in the clean environment. This is an unavailable runtime baseline, not a successful original application run.

A Python 3.12 resolution of the legacy requirements completed. A previous pip-audit of that resolution reported 119 advisory entries in 15 packages: gradio 17; langchain 3; anthropic 1; langchain-community 2; langchain-core 11; langchain-openai 2; langchain-text-splitters 4; langgraph 2; langgraph-checkpoint 6; langgraph-sdk 3; langsmith 5; mcp 10; mem0ai 8; pillow 35; starlette 10. These are advisory entries, not independent exploit demonstrations. The CI job resolves and audits again so changed results stay visible. Migration of that full stack is unfinished.

## Portfolio implementation

Python 3.12.14; uv 0.12.23. New environment isolated with uv.lock.
Local pytest: **9 passed**, including execution of the real controller method body with SDK-boundary doubles. Python compilation of the modified upstream controller passed. Starlette currently emits a TestClient/httpx deprecation warning; no test fails because of it.

The local Chromium download returned a truncated archive in this environment. Therefore local real-browser verification is blocked; the independent GitHub runner installs Chromium and executes the smoke scenario. GitHub Actions run 39302399459 was inspected: the verify job passed all nine tests, Ruff, controller compilation, the real Chromium/API flow, responsive screenshots and the isolated dependency audit. The independent legacy-security job failed with 119 advisory entries in 15 packages, as expected; the overall workflow is not green. Screenshot artifacts come from real execution, never generated mockups.

No LLM/provider credentials, production browser profile, customer records or Smart Visions infrastructure were accessed. The controlled fixture is synthetic. No public deployment, real external-site task, arbitrary browsing benchmark, multi-user security audit or full legacy SDK/model integration has been verified.

## Real screenshot evidence

Captured by the real browser smoke in CI, not generated illustrations:

- [Desktop dashboard](screenshots/workbench-1440.png)
- [Mobile dashboard](screenshots/workbench-320.png)
- [Controlled fixture capture](screenshots/controlled-browser.png)

The dependency license metadata inventory is [dependency-licenses.json](dependency-licenses.json). New environment metadata reports MIT, BSD, Apache-2.0, PSF and MPL-2.0 families; certifi uses MPL-2.0. Preserve their notices and any source-file obligations when distributing modified dependencies. This metadata inventory is not a legal opinion or a completed legacy-stack license review.

## Patch-only remediation feasibility — 2026-10-20

A fresh Python 3.12 dependency resolution was attempted with the inherited requirements unchanged and a `pillow>=12.3.0` security constraint (the patch floor reported in the inspected legacy audit). The resolver rejected the graph: Gradio 5.27.0 requires `pillow>=8.0,<12.0`. Therefore that Pillow patch cannot be applied while retaining the inherited Gradio pin. No version was forced, no package-audit exception was added and no lockfile was presented as resolved.

Reproduction: create a constraint file containing `pillow>=12.3.0`, then run `uv pip compile --python-version 3.12 -c <constraint-file> requirements.txt`. The observed result was `No solution found ... gradio==5.27.0 depends on pillow>=8.0,<12.0 ... requirements are unsatisfiable`. A full Gradio/browser-use/LangChain migration requires compatible UI/controller/provider verification; changing only the version strings would not establish that. The isolated workbench and controlled fixture runner remain independently testable, while the full legacy agent remains a draft release with its blocking audit intact.
