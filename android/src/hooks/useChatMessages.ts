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
 * bubble, filled in live by task.delta chunks as the real Claude response
 * streams in (Phase 2 — see backend/app/orchestrator/claude_orchestrator.py).
 * When a task is answered straight from knowledge (no Claude call; see
 * `served_from_knowledge`), there are no deltas — task.completed fills the
 * bubble directly, same as it did in Phase 1.
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
          messages.push({ id: `pending-${event.task_id}`, role: 'assistant', text: '', pending: true });
          break;
        case 'task.delta': {
          const idx = messages.findIndex((m) => m.id === `pending-${event.task_id}`);
          if (idx >= 0) {
            const chunk = String(event.payload.text ?? '');
            messages[idx] = { ...messages[idx], text: messages[idx].text + chunk };
          }
          break;
        }
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
