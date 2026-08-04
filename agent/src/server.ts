import { randomUUID } from "node:crypto";
import type { ServerResponse } from "node:http";
import Fastify, { type FastifyInstance } from "fastify";
import { loadConfig, type AgentConfig } from "./config.js";
import { verifyAuthorizationHeader } from "./auth.js";
import { buildLlmRuntime, getLlmConfig } from "./llm.js";
import {
  createReportSession,
  type AgentSseEvent,
  type ReportAgentRuntime,
  type ReportSession,
} from "./agent.js";

interface SessionEntry {
  session: ReportSession;
  lastAccess: number;
}

export interface BuildServerOptions {
  config?: AgentConfig;
  /**
   * Factory for the pi runtime used by new sessions. Defaults to fetching the
   * LLM config from the backend (cached). Tests inject a faux runtime here.
   */
  createRuntime?: () => Promise<ReportAgentRuntime>;
}

function writeSse(res: ServerResponse, event: AgentSseEvent): void {
  res.write(`event: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`);
}

export function buildServer(options: BuildServerOptions = {}): FastifyInstance {
  const config = options.config ?? loadConfig();
  const createRuntime =
    options.createRuntime ??
    (async () => {
      const llm = await getLlmConfig(config);
      return buildLlmRuntime(llm);
    });

  const app = Fastify({ logger: true });

  const sessions = new Map<string, SessionEntry>();
  const sweeper = setInterval(() => {
    const now = Date.now();
    for (const [id, entry] of sessions) {
      if (!entry.session.isBusy() && now - entry.lastAccess > config.sessionTtlMs) {
        sessions.delete(id);
      }
    }
  }, 10 * 60 * 1000);
  sweeper.unref();
  app.addHook("onClose", async () => clearInterval(sweeper));

  app.get("/health", async () => ({ ok: true }));

  app.post("/reports/chat", async (request, reply) => {
    const auth = verifyAuthorizationHeader(
      request.headers.authorization,
      config.jwtSecret,
    );
    if (!auth) {
      return reply.code(401).send({ message: "无效或过期的访问令牌" });
    }

    const body = request.body as
      | { conversation_id?: unknown; message?: unknown }
      | null
      | undefined;
    const message = typeof body?.message === "string" ? body.message.trim() : "";
    if (!message) {
      return reply.code(400).send({ message: "message 不能为空" });
    }
    const conversationId =
      typeof body?.conversation_id === "string" && body.conversation_id
        ? body.conversation_id
        : randomUUID();

    // Raw SSE stream: bypass Fastify's response lifecycle.
    reply.hijack();
    const res = reply.raw;
    res.writeHead(200, {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    });
    const emit = (event: AgentSseEvent) => {
      if (!res.destroyed) writeSse(res, event);
    };
    const emitError = (msg: string) => emit({ type: "error", data: { message: msg } });
    // Keep intermediaries (and clients) from timing out on quiet stretches.
    const ping = setInterval(() => {
      if (!res.destroyed) res.write(": ping\n\n");
    }, 15 * 1000);
    request.raw.on("close", () => clearInterval(ping));

    try {
      let entry = sessions.get(conversationId);
      if (!entry) {
        let runtime: ReportAgentRuntime;
        try {
          runtime = await createRuntime();
        } catch (err) {
          emitError(`无法获取 LLM 配置: ${err instanceof Error ? err.message : String(err)}`);
          res.end();
          return reply;
        }
        entry = { session: createReportSession(runtime, config, auth.token), lastAccess: 0 };
        sessions.set(conversationId, entry);
      }
      const { session } = entry;
      session.ctx.token = auth.token; // refresh per request (token may rotate)
      session.ctx.report = null;
      entry.lastAccess = Date.now();

      if (session.isBusy()) {
        emitError("该会话正在处理上一条消息，请稍后再试");
        res.end();
        return reply;
      }

      await session.send(message, emit);

      if (session.ctx.report) {
        emit({ type: "report", data: session.ctx.report });
        session.ctx.report = null;
      }
      emit({ type: "final", data: { conversation_id: conversationId } });
    } catch (err) {
      emitError(err instanceof Error ? err.message : String(err));
    } finally {
      clearInterval(ping);
      if (!res.destroyed) res.end();
    }
    return reply;
  });

  return app;
}

const isMain = process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (isMain) {
  const config = loadConfig();
  const app = buildServer({ config });
  app
    .listen({ port: config.port, host: config.host })
    .then(() => {
      app.log.info(`report-agent listening on ${config.host}:${config.port}`);
    })
    .catch((err) => {
      app.log.error(err);
      process.exit(1);
    });
}
