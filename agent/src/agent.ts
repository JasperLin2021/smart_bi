import { Agent } from "@earendil-works/pi-agent-core";
import type { AgentEvent, StreamFn } from "@earendil-works/pi-agent-core";
import type { Context, Model, SimpleStreamOptions } from "@earendil-works/pi-ai";
import type { AgentConfig } from "./config.js";
import { buildTools, type SessionContext } from "./tools.js";

/** SSE event channel names pushed to the client (contract, do not change). */
export type AgentSseEvent =
  | { type: "trace"; data: { stage: "tool_start" | "tool_end"; tool: string; summary?: string } }
  | { type: "text"; data: { delta: string } }
  | { type: "report"; data: { title: string; html: string } }
  | { type: "final"; data: { conversation_id: string } }
  | { type: "error"; data: { message: string } };

export const SYSTEM_PROMPT = `你是一位资深 BI 报表设计师，为 SmartBI 平台用户生成数据分析报表。

【工作流程】
1. 先调用 list_datasets 查看可用数据集，挑选与用户需求最匹配的数据集。
2. 必要时用 get_dataset_schema 查看字段结构，然后用 query_dataset（或 ask_data_question）取出报表所需的真实数据。可以多次查询以获得不同维度的数据。
3. 基于取到的数据设计并产出一个完整的单文件 HTML 报表，最后必须调用 submit_report 提交。

【取数提示】
- 需要按自然年度/月份口径（如“2017 年”）统计时：优先用 query_dataset 的 filters 限定时间范围，例如 ["order_date >= 2017-01-01", "order_date < 2018-01-01"]；若需按年/月分组展示，使用 get_dataset_schema 返回的时间维度派生 ID，形如 <时间维度ID>_year（年）与 <时间维度ID>_month（月）。
- 维度/指标/过滤字段必须以 get_dataset_schema 返回的语义模型（semantic_model）为准，禁止凭空猜测字段 ID。

【报表设计要求】
- 单文件 HTML：完整 <!DOCTYPE html> 文档，所有 CSS 内联在 <style> 中，不使用任何外部 CSS/字体资源。
- 结构清晰：顶部为报表标题与摘要，KPI 卡片展示关键指标，ECharts 图表呈现趋势/占比/对比，数据表格列出明细。
- 响应式布局：使用 flex/grid 与相对单位，适配桌面与移动宽度；配色专业、克制。
- ECharts 只能且必须通过 <script src="/report-libs/echarts.min.js"></script> 引入，图表初始化脚本写在页面内联 <script> 中。

【硬性约束】
- 禁止引用除 /report-libs/echarts.min.js 之外的任何外部脚本（包括 CDN 上的 echarts、其他 JS 库）。
- 报表中的所有数字、表格与图表数据必须来自工具查询结果，严禁编造或估算数据；查询无数据时如实说明。
- 每次回复都必须以调用 submit_report 提交报表结束；若因数据缺失等原因无法产出报表，也要提交一个说明原因的 HTML 页面。
- 与用户的文字交流使用中文，简明扼要。`;

/** Everything needed to construct a pi Agent for one conversation. */
export interface ReportAgentRuntime {
  model: Model<any>;
  streamFn: StreamFn;
  getApiKey: () => Promise<string>;
  temperature?: number;
}

export interface ReportSession {
  /** Shared tool context; the server refreshes `token` per request. */
  ctx: SessionContext;
  /** True while a run is in flight. */
  isBusy(): boolean;
  /**
   * Run one user message through the agent loop, forwarding progress events
   * to `emit`. Resolves once the loop ends; the submitted report (if any) is
   * emitted as a `report` event by the server afterwards via `ctx.report`.
   */
  send(message: string, emit: (event: AgentSseEvent) => void): Promise<void>;
}

function summarize(value: unknown, max = 160): string {
  let text: string;
  try {
    text = typeof value === "string" ? value : JSON.stringify(value);
  } catch {
    text = String(value);
  }
  if (text.length > max) return `${text.slice(0, max)}…`;
  return text;
}

/** Create a stateful report-agent session (one per conversation_id). */
export function createReportSession(
  runtime: ReportAgentRuntime,
  cfg: AgentConfig,
  token: string,
): ReportSession {
  const ctx: SessionContext = { token, report: null };
  const tools = buildTools(cfg, ctx);

  // Inject the backend-configured temperature into every provider request.
  const streamFn: StreamFn = (
    model: Model<any>,
    context: Context,
    options?: SimpleStreamOptions,
  ) => runtime.streamFn(model, context, { ...options, temperature: runtime.temperature });

  const agent = new Agent({
    initialState: {
      systemPrompt: SYSTEM_PROMPT,
      model: runtime.model,
      tools,
    },
    streamFn,
    getApiKey: runtime.getApiKey,
  });

  return {
    ctx,
    isBusy: () => agent.state.isStreaming,
    async send(message, emit) {
      const unsubscribe = agent.subscribe((event: AgentEvent) => {
        if (
          event.type === "message_update" &&
          event.assistantMessageEvent.type === "text_delta"
        ) {
          emit({ type: "text", data: { delta: event.assistantMessageEvent.delta } });
        } else if (event.type === "tool_execution_start") {
          emit({
            type: "trace",
            data: { stage: "tool_start", tool: event.toolName, summary: summarize(event.args) },
          });
        } else if (event.type === "tool_execution_end") {
          const content = event.result?.content;
          const first = Array.isArray(content) ? content[0] : undefined;
          emit({
            type: "trace",
            data: {
              stage: "tool_end",
              tool: event.toolName,
              summary: summarize(first?.text ?? ""),
            },
          });
        }
      });
      try {
        await agent.prompt(message);
        if (agent.state.errorMessage) {
          throw new Error(agent.state.errorMessage);
        }
      } finally {
        unsubscribe();
      }
    },
  };
}
