import type { JarvisSettings } from '../config/settings';

/**
 * Thin REST client. No business logic — just shaped requests to the
 * backend defined in backend/app/api/routes.py.
 */
export class JarvisApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

export async function request(settings: JarvisSettings, path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`${settings.backendHttpUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(settings.apiToken ? { Authorization: `Bearer ${settings.apiToken}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new JarvisApiError(text || response.statusText, response.status);
  }
  return response;
}

/** GET a JSON endpoint. Returns null on a 503 ("not configured" — see
 * backend/app/api/phase3_routes.py) so screens can render an honest
 * "not available" state instead of an error banner. */
export async function getJson<T>(settings: JarvisSettings, path: string): Promise<T | null> {
  try {
    const response = await request(settings, path);
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof JarvisApiError && error.status === 503) return null;
    throw error;
  }
}

export async function postJson<T>(settings: JarvisSettings, path: string, body: unknown): Promise<T> {
  const response = await request(settings, path, { method: 'POST', body: JSON.stringify(body) });
  return (await response.json()) as T;
}

export async function checkHealth(settings: JarvisSettings): Promise<boolean> {
  try {
    const response = await fetch(`${settings.backendHttpUrl}/health`);
    if (!response.ok) return false;
    const body = await response.json();
    return body?.status === 'ok';
  } catch {
    return false;
  }
}

export async function sendMessage(
  settings: JarvisSettings,
  args: { sessionId: string; project?: string; text: string }
): Promise<{ task_id: string }> {
  const response = await request(settings, '/messages', {
    method: 'POST',
    body: JSON.stringify({ session_id: args.sessionId, project: args.project ?? 'default', text: args.text }),
  });
  return response.json();
}

export async function approveConfirmation(settings: JarvisSettings, confirmationId: string): Promise<void> {
  await request(settings, `/confirmations/${confirmationId}/approve`, { method: 'POST' });
}

export async function rejectConfirmation(settings: JarvisSettings, confirmationId: string): Promise<void> {
  await request(settings, `/confirmations/${confirmationId}/reject`, { method: 'POST' });
}
