/**
 * Aspire AppHost (TypeScript) — orchestrates the whole contract-triage stack:
 *
 *   devui           — Microsoft Agent Framework DevUI      (python)     :8080
 *   api             — FastAPI triage backend (uvicorn)     (python)     :8000
 *   frontend        — Next.js review console               (node)       :3000
 *
 *   langfuse-web    — Langfuse UI + OTLP trace ingest       (container)  :3001
 *   langfuse-worker — Langfuse async ingestion worker       (container)
 *   postgres        — Langfuse metadata                     (container)
 *   clickhouse      — Langfuse trace analytics              (container)
 *   redis           — Langfuse queue                        (container)
 *   minio           — Langfuse S3-compatible blob store     (container)  :9090
 *   storage         — contract-document object store        (container)  :9092
 *
 * The API's own data plane: `storage` (an ephemeral, app-facing MinIO holding
 * the contract intake PDFs, re-seeded from ../test on boot) and a SQLite file
 * (TRIAGE_DB_PATH) that persists triage results and reviewer decisions across
 * restarts. Both are injected into the `api` resource; SQLite needs no server,
 * so it also works under the ../scripts/dev.sh fallback.
 *
 * The agent (devui + api) ships its Microsoft Agent Framework OpenTelemetry
 * traces to langfuse-web's OTLP endpoint, so every triage run — the agent
 * invocation, each LLM `chat`, and each tool call — shows up in Langfuse.
 *
 * The Langfuse stack needs Docker. It is self-contained: langfuse-web is
 * headless-initialised with a fixed org/project/user and API keys, so traces
 * authenticate the moment the containers are healthy — no manual sign-up.
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

// ── Langfuse configuration ──────────────────────────────────────────────────
// Demo credentials — fine for local dev. For anything real, move the secrets to
// `builder.addParameter(name, value, false, /* secret */ true)` and reference
// the same ParameterResource from web, worker and the agent.
const LF_WEB_PORT = 3001; // host port for the Langfuse UI *and* OTLP ingest
const MINIO_API_PORT = 9090; // host port for MinIO (browser-facing presigned URLs)
const MINIO_CONSOLE_PORT = 9091;

// ── Application data plane (contract documents + triage database) ────────────
// A second, app-facing MinIO holds the contract intake PDFs, kept separate from
// Langfuse's internal blob store. It is intentionally *ephemeral* (no volume) —
// an in-memory-style object store the API re-seeds from ../test on every boot.
const STORAGE_API_PORT = 9092; // host port — presigned URLs are browser-facing
const STORAGE_CONSOLE_PORT = 9093;
const STORAGE_USER = 'contract-store';
const STORAGE_PASSWORD = 'contract-store-secret';
const STORAGE_BUCKET = 'contracts';
// SQLite lives on the API's local disk; the path is relative to its cwd (../agent).
const TRIAGE_DB_PATH = '.data/triage.db';

const LF_PUBLIC_KEY = 'pk-lf-contract-triage';
const LF_SECRET_KEY = 'sk-lf-contract-triage';
const LF_ORG_ID = 'northgate';
const LF_PROJECT_ID = 'contract-triage';
const LF_USER_EMAIL = 'admin@northgate.local';
const LF_USER_PASSWORD = 'langfuse-admin'; // Langfuse requires >= 8 chars

const PG_USER = 'postgres';
const PG_PASSWORD = 'postgres';
const PG_DB = 'postgres';
const CH_USER = 'clickhouse';
const CH_PASSWORD = 'clickhouse';
const REDIS_AUTH = 'langfuse-redis';
const MINIO_USER = 'minio';
const MINIO_PASSWORD = 'miniosecret';
const LF_SALT = 'contract-triage-salt';
const LF_ENCRYPTION_KEY = '0'.repeat(64); // 32 bytes hex — swap for `openssl rand -hex 32`
const LF_NEXTAUTH_SECRET = 'contract-triage-nextauth';

const LANGFUSE_WEB_URL = `http://localhost:${LF_WEB_PORT}`;
const OTLP_TRACES_ENDPOINT = `${LANGFUSE_WEB_URL}/api/public/otel/v1/traces`;
// Langfuse authenticates OTLP with Basic <base64("publicKey:secretKey")>.
const OTLP_AUTH = 'Basic ' + Buffer.from(`${LF_PUBLIC_KEY}:${LF_SECRET_KEY}`).toString('base64');

// ── Langfuse backing services ───────────────────────────────────────────────
// Containers reach each other by resource name on the Aspire network, so the
// hostnames below (postgres, clickhouse, redis, minio) resolve internally.
const postgres = await builder
  .addContainer('postgres', { Image: 'postgres', Tag: '17' })
  .withEnvironment('POSTGRES_USER', PG_USER)
  .withEnvironment('POSTGRES_PASSWORD', PG_PASSWORD)
  .withEnvironment('POSTGRES_DB', PG_DB)
  .withVolume('langfuse-postgres', '/var/lib/postgresql/data');

const clickhouse = await builder
  .addContainer('clickhouse', { Image: 'clickhouse/clickhouse-server', Tag: '24.8' })
  .withEnvironment('CLICKHOUSE_DB', 'default')
  .withEnvironment('CLICKHOUSE_USER', CH_USER)
  .withEnvironment('CLICKHOUSE_PASSWORD', CH_PASSWORD)
  .withVolume('langfuse-clickhouse', '/var/lib/clickhouse');

const redis = await builder
  .addContainer('redis', { Image: 'redis', Tag: '7' })
  .withArgs('--requirepass', REDIS_AUTH, '--maxmemory-policy', 'noeviction')
  .withVolume('langfuse-redis', '/data');

// MinIO: create the `langfuse` bucket up front, then serve S3 (:9000) + console (:9001).
const minio = await builder
  .addContainer('minio', { Image: 'minio/minio', Tag: 'latest' })
  .withEntrypoint('sh')
  .withArgs('-c', 'mkdir -p /data/langfuse && minio server /data --address ":9000" --console-address ":9001"')
  .withEnvironment('MINIO_ROOT_USER', MINIO_USER)
  .withEnvironment('MINIO_ROOT_PASSWORD', MINIO_PASSWORD)
  .withHttpEndpoint({ port: MINIO_API_PORT, targetPort: 9000, name: 'api' })
  .withHttpEndpoint({ port: MINIO_CONSOLE_PORT, targetPort: 9001, name: 'console' })
  .withVolume('langfuse-minio', '/data');

// ── Contract document store (app-facing, ephemeral MinIO) ───────────────────
// Creates the `contracts` bucket up front, then serves S3 (:9000) + console
// (:9001). No .withVolume — the store is in-memory-style and re-seeded on boot.
const storage = await builder
  .addContainer('storage', { Image: 'minio/minio', Tag: 'latest' })
  .withEntrypoint('sh')
  .withArgs(
    '-c',
    `mkdir -p /data/${STORAGE_BUCKET} && minio server /data --address ":9000" --console-address ":9001"`,
  )
  .withEnvironment('MINIO_ROOT_USER', STORAGE_USER)
  .withEnvironment('MINIO_ROOT_PASSWORD', STORAGE_PASSWORD)
  .withHttpEndpoint({ port: STORAGE_API_PORT, targetPort: 9000, name: 'api' })
  .withHttpEndpoint({ port: STORAGE_CONSOLE_PORT, targetPort: 9001, name: 'console' })
  .withExternalHttpEndpoints();

// Data-plane env injected into the API: the object store (host-facing, so the
// API signs URLs the browser can open) and the SQLite path.
const dataEnv: [string, string][] = [
  ['CONTRACT_STORE_ENDPOINT', `localhost:${STORAGE_API_PORT}`],
  ['CONTRACT_STORE_ACCESS_KEY', STORAGE_USER],
  ['CONTRACT_STORE_SECRET_KEY', STORAGE_PASSWORD],
  ['CONTRACT_STORE_BUCKET', STORAGE_BUCKET],
  ['CONTRACT_STORE_SECURE', 'false'],
  ['CONTRACT_STORE_SEED_DIR', '../test'], // <ITEM_ID>/*.pdf, relative to ../agent
  ['TRIAGE_DB_PATH', TRIAGE_DB_PATH],
];

// Env shared by langfuse-web and langfuse-worker (the compose "worker-env" anchor).
const langfuseCoreEnv: [string, string][] = [
  ['DATABASE_URL', `postgresql://${PG_USER}:${PG_PASSWORD}@postgres:5432/${PG_DB}`],
  ['SALT', LF_SALT],
  ['ENCRYPTION_KEY', LF_ENCRYPTION_KEY],
  ['TELEMETRY_ENABLED', 'false'],
  ['CLICKHOUSE_MIGRATION_URL', 'clickhouse://clickhouse:9000'],
  ['CLICKHOUSE_URL', 'http://clickhouse:8123'],
  ['CLICKHOUSE_USER', CH_USER],
  ['CLICKHOUSE_PASSWORD', CH_PASSWORD],
  ['CLICKHOUSE_CLUSTER_ENABLED', 'false'],
  ['REDIS_HOST', 'redis'],
  ['REDIS_PORT', '6379'],
  ['REDIS_AUTH', REDIS_AUTH],
  ['LANGFUSE_S3_EVENT_UPLOAD_BUCKET', 'langfuse'],
  ['LANGFUSE_S3_EVENT_UPLOAD_REGION', 'auto'],
  ['LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT', 'http://minio:9000'],
  ['LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID', MINIO_USER],
  ['LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY', MINIO_PASSWORD],
  ['LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE', 'true'],
  ['LANGFUSE_S3_MEDIA_UPLOAD_BUCKET', 'langfuse'],
  ['LANGFUSE_S3_MEDIA_UPLOAD_REGION', 'auto'],
  // Media URLs are presigned for the browser, so this endpoint is host-facing.
  ['LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT', `http://localhost:${MINIO_API_PORT}`],
  ['LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID', MINIO_USER],
  ['LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY', MINIO_PASSWORD],
  ['LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE', 'true'],
];

// ── Langfuse worker (async ingestion → ClickHouse) ──────────────────────────
let langfuseWorker = await builder.addContainer('langfuse-worker', {
  Image: 'langfuse/langfuse-worker',
  Tag: '3',
});
for (const [key, value] of langfuseCoreEnv) {
  langfuseWorker = langfuseWorker.withEnvironment(key, value);
}
langfuseWorker = langfuseWorker
  .waitFor(postgres)
  .waitFor(clickhouse)
  .waitFor(redis)
  .waitFor(minio);

// ── Langfuse web (UI + OTLP ingest, headless-initialised) ───────────────────
let langfuseWeb = await builder.addContainer('langfuse-web', {
  Image: 'langfuse/langfuse',
  Tag: '3',
});
for (const [key, value] of langfuseCoreEnv) {
  langfuseWeb = langfuseWeb.withEnvironment(key, value);
}
langfuseWeb = langfuseWeb
  .withEnvironment('NEXTAUTH_URL', LANGFUSE_WEB_URL)
  .withEnvironment('NEXTAUTH_SECRET', LF_NEXTAUTH_SECRET)
  // Headless init — provisions the org/project/user and the API keys the agent
  // authenticates its OTLP traces with, so nothing needs setting up in the UI.
  .withEnvironment('LANGFUSE_INIT_ORG_ID', LF_ORG_ID)
  .withEnvironment('LANGFUSE_INIT_ORG_NAME', 'Northgate')
  .withEnvironment('LANGFUSE_INIT_PROJECT_ID', LF_PROJECT_ID)
  .withEnvironment('LANGFUSE_INIT_PROJECT_NAME', 'Contract Triage')
  .withEnvironment('LANGFUSE_INIT_PROJECT_PUBLIC_KEY', LF_PUBLIC_KEY)
  .withEnvironment('LANGFUSE_INIT_PROJECT_SECRET_KEY', LF_SECRET_KEY)
  .withEnvironment('LANGFUSE_INIT_USER_EMAIL', LF_USER_EMAIL)
  .withEnvironment('LANGFUSE_INIT_USER_NAME', 'Northgate Admin')
  .withEnvironment('LANGFUSE_INIT_USER_PASSWORD', LF_USER_PASSWORD)
  .withHttpEndpoint({ port: LF_WEB_PORT, targetPort: 3000, name: 'http' })
  .withExternalHttpEndpoints()
  .waitFor(postgres)
  .waitFor(clickhouse)
  .waitFor(redis)
  .waitFor(minio);

// OpenTelemetry env injected into both Python resources. The agent buffers and
// retries, so it starts immediately and traces begin flowing once Langfuse is up
// (no waitFor on langfuse-web — the app stays usable while it boots).
//
// ENABLE_SENSITIVE_DATA captures prompts/responses/tool args — great for a demo,
// but keep it off in production. See agent/contract_triage/observability.py.
const otelEnv = (serviceName: string): [string, string][] => [
  ['ENABLE_OTEL', 'true'],
  ['ENABLE_INSTRUMENTATION', 'true'],
  ['ENABLE_SENSITIVE_DATA', 'true'],
  ['OTEL_SERVICE_NAME', serviceName],
  ['OTEL_EXPORTER_OTLP_TRACES_ENDPOINT', OTLP_TRACES_ENDPOINT],
  ['OTEL_EXPORTER_OTLP_TRACES_PROTOCOL', 'http/protobuf'],
  ['OTEL_EXPORTER_OTLP_TRACES_HEADERS', `Authorization=${OTLP_AUTH}`],
];

// ── Agent Framework DevUI (python) ─────────────────────────────────────────
let devui = await builder
  .addPythonApp('devui', AGENT_DIR, '-m', 'contract_triage.devui_app')
  .withVirtualEnvironment(`${AGENT_DIR}/.venv`)
  .withHttpEndpoint({ port: 8080, env: 'DEVUI_PORT' })
  .withExternalHttpEndpoints();
for (const [key, value] of otelEnv('contract-triage-devui')) {
  devui = devui.withEnvironment(key, value);
}

// ── FastAPI triage backend (uvicorn ASGI) ──────────────────────────────────
let api = await builder
  .addUvicornApp('api', AGENT_DIR, 'contract_triage.api:app')
  .withVirtualEnvironment(`${AGENT_DIR}/.venv`)
  .withHttpEndpoint({ port: 8000, env: 'PORT' })
  .withExternalHttpEndpoints()
  // Wait for the object store so the startup seed lands its documents.
  .waitFor(storage);
for (const [key, value] of [...otelEnv('contract-triage-api'), ...dataEnv]) {
  api = api.withEnvironment(key, value);
}

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
