/**
 * End-to-end smoke test for the report agent service.
 *
 * - Stub backend: serves /api/internal/llm-config + data endpoints, records auth headers.
 * - LLM: pi-ai fauxProvider with a scripted report-generation loop (no API key needed).
 * - Assertions: /health, 401s, full SSE frame sequence for POST /reports/chat.
 *
 * Run after `npm run build`:  node test/smoke.mjs
 */
import assert from "node:assert/strict";
import http from "node:http";
import jwt from "jsonwebtoken";
import {
  createModels,
  fauxAssistantMessage,
  fauxProvider,
  fauxText,
  fauxToolCall,
} from "@earendil-works/pi-ai";
import { buildServer } from "../dist/server.js";
import { loadConfig } from "../dist/config.js";
import { getLlmConfig } from "../dist/llm.js";

const JWT_SECRET = "smoke-test-secret";
const INTERNAL_SECRET = "smoke-internal-secret";

const REPORT_HTML = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>销售月报</title>
<style>body{font-family:sans-serif;margin:0;padding:16px}.kpi{display:flex;gap:12px;flex-wrap:wrap}.card{flex:1;min-width:160px;border:1px solid #e5e7eb;border-radius:8px;padding:12px}table{width:100%;border-collapse:collapse}td,th{border:1px solid #e5e7eb;padding:6px}#chart{width:100%;height:320px}</style>
</head><body>
<h1>销售月报</h1>
<div class="kpi"><div class="card"><div>总销售额</div><b>300</b></div></div>
<div id="chart"></div>
<table><tr><th>月份</th><th>销售额</th></tr><tr><td>1月</td><td>100</td></tr><tr><td>2月</td><td>200</td></tr></table>
<script src="/report-libs/echarts.min.js"></script>
<script>const c=echarts.init(document.getElementById('chart'));c.setOption({xAxis:{type:'category',data:['1月','2月']},yAxis:{},series:[{type:'bar',data:[100,200]}]});</script>
</body></html>`;

// ---- stub backend ----------------------------------------------------------
const backendCalls = [];
const stubBackend = http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (c) => chunks.push(c));
  req.on("end", () => {
    const body = Buffer.concat(chunks).toString("utf8");
    backendCalls.push({
      url: req.url,
      method: req.method,
      authorization: req.headers.authorization,
      internalSecret: req.headers["x-internal-secret"],
      body,
    });
    res.setHeader("Content-Type", "application/json");
    if (req.url === "/api/internal/llm-config") {
      assert.equal(req.headers["x-internal-secret"], INTERNAL_SECRET);
      res.end(
        JSON.stringify({
          provider: "custom",
          base_url: "http://unused.invalid/v1",
          api_key: "unused",
          model: "faux-model",
          temperature: 0.3,
        }),
      );
    } else if (req.url === "/api/datasets") {
      res.end(JSON.stringify([{ id: "ds1", name: "销售数据" }]));
    } else if (req.url === "/api/query/semantic") {
      res.end(
        JSON.stringify({ rows: [{ month: "1月", sales: 100 }, { month: "2月", sales: 200 }] }),
      );
    } else {
      res.statusCode = 404;
      res.end(JSON.stringify({ error: "not found" }));
    }
  });
});
await new Promise((resolve) => stubBackend.listen(0, "127.0.0.1", resolve));
const backendUrl = `http://127.0.0.1:${stubBackend.address().port}`;

// ---- faux LLM runtime ------------------------------------------------------
const faux = fauxProvider({ tokensPerSecond: 10000 });
const models = createModels();
models.setProvider(faux.provider);
faux.setResponses([
  fauxAssistantMessage([fauxToolCall("list_datasets", {})], { stopReason: "toolUse" }),
  fauxAssistantMessage(
    [
      fauxToolCall("query_dataset", {
        dataset_id: "ds1",
        dimensions: ["month"],
        metrics: ["sales"],
        filters: [],
        limit: 10,
      }),
    ],
    { stopReason: "toolUse" },
  ),
  fauxAssistantMessage(
    [
      fauxText("数据已取到，正在生成报表。"),
      fauxToolCall("submit_report", { title: "销售月报", html: REPORT_HTML }),
    ],
    { stopReason: "toolUse" },
  ),
  fauxAssistantMessage([fauxText("报表已生成并提交。")]),
]);

const config = {
  ...loadConfig({}),
  jwtSecret: JWT_SECRET,
  backendUrl,
  internalApiSecret: INTERNAL_SECRET,
};
const app = buildServer({
  config,
  createRuntime: async () => {
    // Exercise the real llm.ts fetch+cache path against the stub backend,
    // then hand the agent a faux (scripted) model instead of a real LLM.
    const llmCfg = await getLlmConfig(config);
    assert.equal(llmCfg.model, "faux-model");
    return {
      model: faux.getModel(),
      streamFn: models.streamSimple.bind(models),
      getApiKey: async () => "faux",
      temperature: llmCfg.temperature,
    };
  },
});
await app.listen({ port: 0, host: "127.0.0.1" });
const base = `http://127.0.0.1:${app.server.address().port}`;

let passed = 0;
function ok(name, cond) {
  assert.ok(cond, name);
  passed += 1;
  console.log(`  ✓ ${name}`);
}

// ---- 1. /health ------------------------------------------------------------
{
  const res = await fetch(`${base}/health`);
  const body = await res.json();
  ok("GET /health -> 200 {ok:true}", res.status === 200 && body.ok === true);
}

// ---- 2. auth rejections ----------------------------------------------------
{
  const res = await fetch(`${base}/reports/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: "hi" }),
  });
  ok("POST /reports/chat without token -> 401", res.status === 401);

  const bad = await fetch(`${base}/reports/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer not-a-jwt" },
    body: JSON.stringify({ message: "hi" }),
  });
  ok("POST /reports/chat with invalid token -> 401", bad.status === 401);

  const wrongAlg = jwt.sign({ sub: "u1" }, JWT_SECRET, { algorithm: "HS512" });
  const badAlg = await fetch(`${base}/reports/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${wrongAlg}` },
    body: JSON.stringify({ message: "hi" }),
  });
  ok("POST /reports/chat with HS512 token -> 401 (HS256 only)", badAlg.status === 401);
}

// ---- 3. full SSE chat loop -------------------------------------------------
{
  const token = jwt.sign({ sub: "user-42" }, JWT_SECRET, { algorithm: "HS256" });
  const res = await fetch(`${base}/reports/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message: "帮我做一份销售月报" }),
  });
  ok("POST /reports/chat -> 200", res.status === 200);
  ok(
    "response headers: Cache-Control/X-Accel-Buffering",
    res.headers.get("cache-control") === "no-cache" &&
      res.headers.get("x-accel-buffering") === "no",
  );
  ok(
    "content-type is text/event-stream",
    (res.headers.get("content-type") ?? "").includes("text/event-stream"),
  );

  const raw = await res.text();
  // Parse SSE frames: "event: X\ndata: {json}\n\n" (ignore ": ping" comments)
  const frames = [];
  for (const block of raw.split("\n\n")) {
    if (!block || block.startsWith(":")) continue;
    const m = /^event: (\w+)\ndata: (.*)$/s.exec(block);
    assert.ok(m, `malformed SSE frame: ${JSON.stringify(block)}`);
    frames.push({ event: m[1], data: JSON.parse(m[2]) });
  }
  ok("all frames match 'event: X\\ndata: {json}' wire format", frames.length > 0);

  const toolStarts = frames.filter((f) => f.event === "trace" && f.data.stage === "tool_start");
  const startedTools = toolStarts.map((f) => f.data.tool);
  ok(
    "trace tool_start for list_datasets/query_dataset/submit_report",
    ["list_datasets", "query_dataset", "submit_report"].every((t) => startedTools.includes(t)),
  );
  const toolEnds = frames.filter((f) => f.event === "trace" && f.data.stage === "tool_end");
  ok("trace tool_end emitted for each tool", toolEnds.length >= 3);

  const textDelta = frames
    .filter((f) => f.event === "text")
    .map((f) => f.data.delta)
    .join("");
  ok("text deltas stream assistant prose", textDelta.includes("数据已取到"));

  const report = frames.find((f) => f.event === "report");
  ok("report event emitted", !!report);
  ok(
    "report payload {title, html} with echarts script",
    report.data.title === "销售月报" &&
      report.data.html.includes("/report-libs/echarts.min.js"),
  );

  const final = frames.at(-1);
  ok(
    "final frame is last and carries conversation_id",
    final.event === "final" && typeof final.data.conversation_id === "string",
  );

  ok("no error frames", !frames.some((f) => f.event === "error"));

  // Bearer token passthrough to the backend data tools
  const datasetCall = backendCalls.find((c) => c.url === "/api/datasets");
  ok(
    "data tools passthrough the original Bearer token",
    datasetCall && datasetCall.authorization === `Bearer ${token}`,
  );
  const semanticCall = backendCalls.find((c) => c.url === "/api/query/semantic");
  ok(
    "query_dataset forwarded body {dataset_id, dimensions, metrics, filters, limit}",
    semanticCall &&
      JSON.stringify(JSON.parse(semanticCall.body)) ===
        JSON.stringify({
          dataset_id: "ds1",
          dimensions: ["month"],
          metrics: ["sales"],
          filters: [],
          limit: 10,
        }),
  );
  ok(
    "llm-config fetched with X-Internal-Secret",
    backendCalls.some(
      (c) => c.url === "/api/internal/llm-config" && c.internalSecret === INTERNAL_SECRET,
    ),
  );
}

await app.close();
stubBackend.close();
console.log(`\nSMOKE OK — ${passed} assertions passed`);
