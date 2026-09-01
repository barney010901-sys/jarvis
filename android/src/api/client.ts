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

async function request(settings: JarvisSettings, path: string, init: RequestInit = {}) {
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
