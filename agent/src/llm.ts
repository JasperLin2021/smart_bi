import {
  createModels,
  createProvider,
  type Model,
  type MutableModels,
} from "@earendil-works/pi-ai";
import { openAICompletionsApi } from "@earendil-works/pi-ai/api/openai-completions.lazy";
import type { AgentConfig } from "./config.js";

/** LLM configuration as returned by the SmartBI backend internal endpoint. */
export interface LlmConfig {
  provider: string;
  base_url: string;
  api_key: string;
  model: string;
  temperature: number;
}

interface CacheEntry {
  config: LlmConfig;
  fetchedAt: number;
}

let cache: CacheEntry | null = null;
let inflight: Promise<LlmConfig> | null = null;

async function fetchLlmConfig(cfg: AgentConfig): Promise<LlmConfig> {
  const res = await fetch(`${cfg.backendUrl}/api/internal/llm-config`, {
    headers: { "X-Internal-Secret": cfg.internalApiSecret },
    signal: AbortSignal.timeout(cfg.backendTimeoutMs),
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch LLM config: backend responded ${res.status}`);
  }
  const body = (await res.json()) as Partial<LlmConfig>;
  if (!body.base_url || !body.api_key || !body.model) {
    throw new Error("LLM config response is missing base_url/api_key/model");
  }
  return {
    provider: body.provider ?? "custom",
    base_url: body.base_url,
    api_key: body.api_key,
    model: body.model,
    temperature: typeof body.temperature === "number" ? body.temperature : 0.7,
  };
}

/** Fetch the LLM config from the backend, cached for `llmConfigCacheMs`. */
export async function getLlmConfig(cfg: AgentConfig): Promise<LlmConfig> {
  const now = Date.now();
  if (cache && now - cache.fetchedAt < cfg.llmConfigCacheMs) {
    return cache.config;
  }
  if (!inflight) {
    inflight = fetchLlmConfig(cfg)
      .then((config) => {
        cache = { config, fetchedAt: Date.now() };
        return config;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

/** Test hook: drop the cached LLM config. */
export function resetLlmConfigCache(): void {
  cache = null;
  inflight = null;
}

export interface LlmRuntime {
  /** pi-ai model registered under the in-process "user-llm" provider. */
  model: Model<"openai-completions">;
  /** streamSimple bound to a Models collection holding the user-llm provider. */
  streamFn: MutableModels["streamSimple"];
  /** API key resolver for the Agent. */
  getApiKey: () => Promise<string>;
  /** Temperature from the backend LLM config. */
  temperature: number;
}

/** Build the pi-ai runtime (model + provider + stream function) from the LLM config. */
export function buildLlmRuntime(llm: LlmConfig): LlmRuntime {
  const model: Model<"openai-completions"> = {
    id: llm.model,
    name: llm.model,
    api: "openai-completions",
    provider: "user-llm",
    baseUrl: llm.base_url,
    reasoning: false,
    input: ["text"],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 131072,
    maxTokens: 8192,
    compat: { supportsDeveloperRole: false, supportsReasoningEffort: false },
  };
  const provider = createProvider({
    id: "user-llm",
    auth: {
      apiKey: {
        name: "User key",
        resolve: async () => ({ auth: { apiKey: llm.api_key } }),
      },
    },
    models: [model],
    api: openAICompletionsApi(),
  });
  const models = createModels();
  models.setProvider(provider);
  return {
    model,
    streamFn: models.streamSimple.bind(models),
    getApiKey: async () => llm.api_key,
    temperature: llm.temperature,
  };
}
