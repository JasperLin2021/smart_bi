import { Type } from "@earendil-works/pi-ai";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import type { AgentConfig } from "./config.js";

/** Mutable per-conversation context shared by all tools of one session. */
export interface SessionContext {
  /** Raw Bearer token of the current request, passed through to the backend. */
  token: string;
  /** Report submitted via submit_report; read by the server after the run. */
  report: { title: string; html: string } | null;
}

const MAX_HTML_BYTES = 500 * 1024;
const ECHARTS_SRC = "/report-libs/echarts.min.js";

async function callBackend(
  cfg: AgentConfig,
  ctx: SessionContext,
  path: string,
  init: RequestInit = {},
): Promise<unknown> {
  const res = await fetch(`${cfg.backendUrl}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${ctx.token}`,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    signal: AbortSignal.timeout(cfg.backendTimeoutMs),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `Backend ${init.method ?? "GET"} ${path} failed with ${res.status}: ${body.slice(0, 300)}`,
    );
  }
  return res.json();
}

function textResult(text: string, details: Record<string, unknown> = {}) {
  return { content: [{ type: "text" as const, text }], details };
}

/** Build the five pi-agent-core tools bound to one session context. */
export function buildTools(cfg: AgentConfig, ctx: SessionContext): AgentTool<any>[] {
  const listDatasets: AgentTool = {
    name: "list_datasets",
    label: "列出数据集",
    description: "列出当前用户可用的全部数据集（id、名称、描述）。每次任务开始时必须先调用它来选择合适的数据集。",
    parameters: Type.Object({}),
    execute: async () => {
      const data = await callBackend(cfg, ctx, "/api/datasets");
      return textResult(JSON.stringify(data));
    },
  };

  const getDatasetSchemaParams = Type.Object({
    dataset_id: Type.String({ description: "数据集 ID" }),
  });
  const getDatasetSchema: AgentTool<typeof getDatasetSchemaParams> = {
    name: "get_dataset_schema",
    label: "查看数据集结构",
    description: "查看指定数据集的字段结构（维度、指标及其类型），用于规划查询。",
    parameters: getDatasetSchemaParams,
    execute: async (_id, params) => {
      const data = await callBackend(cfg, ctx, `/api/datasets/${encodeURIComponent(params.dataset_id)}`);
      return textResult(JSON.stringify(data));
    },
  };

  const queryDatasetParams = Type.Object({
    dataset_id: Type.String({ description: "数据集 ID" }),
    dimensions: Type.Array(Type.String(), { description: "分组维度字段名列表，可为空数组" }),
    metrics: Type.Array(Type.String(), { description: "聚合指标字段名列表" }),
    filters: Type.Array(Type.String(), { description: "过滤条件列表，可为空数组" }),
    limit: Type.Number({ description: "最大返回行数" }),
  });
  const queryDataset: AgentTool<typeof queryDatasetParams> = {
    name: "query_dataset",
    label: "查询数据集",
    description: "按维度/指标/过滤条件查询数据集，返回结构化数据行。报表中的所有数据必须来自该工具的返回结果。",
    parameters: queryDatasetParams,
    execute: async (_id, params) => {
      const data = await callBackend(cfg, ctx, "/api/query/semantic", {
        method: "POST",
        body: JSON.stringify({
          dataset_id: params.dataset_id,
          dimensions: params.dimensions,
          metrics: params.metrics,
          filters: params.filters,
          limit: params.limit,
        }),
      });
      return textResult(JSON.stringify(data));
    },
  };

  const askDataQuestionParams = Type.Object({
    question: Type.String({ description: "自然语言问题" }),
  });
  const askDataQuestion: AgentTool<typeof askDataQuestionParams> = {
    name: "ask_data_question",
    label: "自然语言取数",
    description: "用自然语言向数据平台提问取数（text2sql）。适合查询条件复杂、难以用维度/指标表达的场景。",
    parameters: askDataQuestionParams,
    execute: async (_id, params) => {
      const data = await callBackend(cfg, ctx, "/api/query/ask", {
        method: "POST",
        body: JSON.stringify({ question: params.question }),
      });
      return textResult(JSON.stringify(data));
    },
  };

  const submitReportParams = Type.Object({
    title: Type.String({ description: "报表标题" }),
    html: Type.String({ description: "完整的单文件 HTML 报表文档" }),
  });
  const submitReport: AgentTool<typeof submitReportParams> = {
    name: "submit_report",
    label: "提交报表",
    description:
      "提交最终报表。html 必须是一个完整的单文件 HTML 文档：内联 CSS，包含 KPI 卡片、ECharts 图表和数据表格，响应式布局；只允许通过 <script src=\"/report-libs/echarts.min.js\"></script> 引入 ECharts，禁止任何其他外链脚本。这是产出报表的唯一方式。",
    parameters: submitReportParams,
    execute: async (_id, params) => {
      const { title, html } = params;
      if (!title || !title.trim()) {
        throw new Error("submit_report: title 不能为空");
      }
      if (!html || !html.trim()) {
        throw new Error("submit_report: html 不能为空");
      }
      const bytes = Buffer.byteLength(html, "utf8");
      if (bytes > MAX_HTML_BYTES) {
        throw new Error(`submit_report: html 大小 ${bytes} 字节超过 500KB 上限`);
      }
      if (!html.includes(ECHARTS_SRC)) {
        throw new Error(
          `submit_report: html 必须包含 <script src="${ECHARTS_SRC}"></script> 以引入 ECharts`,
        );
      }
      ctx.report = { title: title.trim(), html };
      return textResult("报表已提交成功，将被发送给用户。", { title: title.trim(), bytes });
    },
  };

  return [listDatasets, getDatasetSchema, queryDataset, askDataQuestion, submitReport];
}
