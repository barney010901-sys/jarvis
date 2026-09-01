import { useMemo } from 'react';
import type { JarvisEvent } from '../api/events';

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  isError?: boolean;
  pending?: boolean;
};

/**
 * Projects the raw event log into chat turns. A task.created with no
 * matching task.completed/task.failed yet renders as a pending assistant
 * bubble — this is the "streaming assistant response" placeholder until
 * Phase 2 streams real token-by-token text (see agent/provider/base.py).
 */
export function useChatMessages(events: JarvisEvent[]): ChatMessage[] {
  return useMemo(() => {
    const messages: ChatMessage[] = [];
    let openTaskId: string | null = null;

    for (const event of events) {
      switch (event.type) {
        case 'user.message':
          messages.push({ id: event.id, role: 'user', text: String(event.payload.text ?? '') });
          break;
        case 'task.created':
          openTaskId = event.task_id;
          messages.push({ id: `pending-${event.task_id}`, role: 'assistant', text: 'Working on it…', pending: true });
          break;
        case 'task.completed': {
          const idx = messages.findIndex((m) => m.id === `pending-${event.task_id}`);
          const text = String(event.payload.response ?? 'Done.');
          if (idx >= 0) messages[idx] = { id: event.id, role: 'assistant', text };
          else messages.push({ id: event.id, role: 'assistant', text });
          if (event.task_id === openTaskId) openTaskId = null;
          break;
        }
        case 'task.failed': {
          const idx = messages.findIndex((m) => m.id === `pending-${event.task_id}`);
          const text = `Task failed at ${event.payload.stage ?? 'unknown stage'}: ${event.payload.error ?? 'unknown error'}`;
          if (idx >= 0) messages[idx] = { id: event.id, role: 'assistant', text, isError: true };
          else messages.push({ id: event.id, role: 'assistant', text, isError: true });
          if (event.task_id === openTaskId) openTaskId = null;
          break;
        }
        default:
          break;
      }
    }

    return messages;
  }, [events]);
}
