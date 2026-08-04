import jwt from "jsonwebtoken";

export interface AuthContext {
  /** user_id from the JWT `sub` claim. */
  userId: string;
  /** The raw Bearer token, passed through to backend data tool calls. */
  token: string;
}

/**
 * Verify an `Authorization: Bearer <JWT>` header value.
 * Returns null when the header is missing/malformed or the token is invalid.
 */
export function verifyAuthorizationHeader(
  header: string | undefined,
  secret: string,
): AuthContext | null {
  if (!header) return null;
  const match = /^Bearer\s+(.+)$/i.exec(header.trim());
  if (!match) return null;
  const token = match[1];
  try {
    const payload = jwt.verify(token, secret, { algorithms: ["HS256"] });
    if (typeof payload === "string" || typeof payload.sub !== "string" || !payload.sub) {
      return null;
    }
    return { userId: payload.sub, token };
  } catch {
    return null;
  }
}
