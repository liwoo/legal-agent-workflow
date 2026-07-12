/**
 * Aspire AppHost (TypeScript) — orchestrates the whole contract-triage stack:
 *
 *   devui     — Microsoft Agent Framework DevUI        (python)  :8080
 *   api       — FastAPI triage backend (uvicorn/ASGI)  (python)  :8000
 *   frontend  — Next.js review console                 (node)    :3000
 *
 * `aspire run` generates the typed SDK under ./.aspire/modules from
 * aspire.config.json, then starts every resource plus the Aspire dashboard.
 *
 * NB: the TypeScript AppHost is a young, fast-moving surface. If a builder
 * method name differs in your installed Aspire, run `aspire run` once — it
 * regenerates ./.aspire/modules and surfaces the exact API — or use the plain
 * `../scripts/dev.sh` fallback documented in the root README.
 */
import { createBuilder } from './.aspire/modules/aspire.mjs';

const builder = await createBuilder();

const AGENT_DIR = '../agent';
const FRONTEND_DIR = '../frontend';

// ── Agent Framework DevUI (python) ─────────────────────────────────────────
const devui = await builder
  .addPythonApp('devui', AGENT_DIR, '-m', 'contract_triage.devui_app')
  .withVirtualEnvironment(`${AGENT_DIR}/.venv`)
  .withHttpEndpoint({ port: 8080, env: 'DEVUI_PORT' })
  .withExternalHttpEndpoints();

// ── FastAPI triage backend (uvicorn ASGI) ──────────────────────────────────
const api = await builder
  .addUvicornApp('api', AGENT_DIR, 'contract_triage.api:app')
  .withVirtualEnvironment(`${AGENT_DIR}/.venv`)
  .withHttpEndpoint({ port: 8000, env: 'PORT' })
  .withExternalHttpEndpoints();

// ── Next.js review console (node) ──────────────────────────────────────────
// Service discovery: withReference(api) injects the backend endpoint; we also
// map it to the NEXT_PUBLIC_* vars the browser bundle reads.
await builder
  .addJavaScriptApp('frontend', FRONTEND_DIR)
  .withRunScript('dev')
  .withReference(api)
  .withReference(devui)
  .withEnvironment('NEXT_PUBLIC_API_BASE_URL', await api.getEndpoint('http'))
  .withEnvironment('NEXT_PUBLIC_DEVUI_URL', await devui.getEndpoint('http'))
  .withHttpEndpoint({ port: 3000, env: 'PORT' })
  .withExternalHttpEndpoints()
  .waitFor(api);

await builder.build().run();
