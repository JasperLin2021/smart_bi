/**
 * Centralized environment configuration for the report agent service.
 */
export interface AgentConfig {
  /** HTTP listen port. */
  port: number;
  /** HTTP listen host. */
  host: string;
  /** HS256 JWT secret shared with the SmartBI backend. */
  jwtSecret: string;
  /** Base URL of the SmartBI backend API (no trailing slash). */
  backendUrl: string;
  /** Shared secret for backend internal endpoints (X-Internal-Secret). */
  internalApiSecret: string;
  /** LLM config cache TTL in milliseconds. */
  llmConfigCacheMs: number;
  /** Idle session TTL in milliseconds. */
  sessionTtlMs: number;
  /** Timeout for backend data tool calls in milliseconds. */
  backendTimeoutMs: number;
}

function intFromEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  if (Number.isNaN(parsed)) {
    throw new Error(`Invalid integer for env ${name}: ${raw}`);
  }
  return parsed;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AgentConfig {
  return {
    port: intFromEnv("PORT", 8010),
    host: env.HOST ?? "0.0.0.0",
    // Defaults match the docker-compose.dev.yml dev-only values so local
    // processes (e.g. pm2) work without extra env wiring. Always override in
    // any shared environment.
    jwtSecret: env.JWT_SECRET ?? "dev_only_replace_if_shared",
    backendUrl: (env.BACKEND_URL ?? "http://localhost:8002").replace(/\/+$/, ""),
    internalApiSecret: env.INTERNAL_API_SECRET ?? "dev_only_internal_secret",
    llmConfigCacheMs: intFromEnv("LLM_CONFIG_CACHE_MS", 5 * 60 * 1000),
    sessionTtlMs: intFromEnv("SESSION_TTL_MS", 2 * 60 * 60 * 1000),
    backendTimeoutMs: intFromEnv("BACKEND_TIMEOUT_MS", 30 * 1000),
  };
}
