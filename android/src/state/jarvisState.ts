import { useMemo } from 'react';
import type { JarvisEvent } from '../api/events';
import type { ConnectionStatus } from '../hooks/useJarvisSocket';

export type JarvisState =
  | 'IDLE'
  | 'LISTENING'
  | 'THINKING'
  | 'PROCESSING'
  | 'USING_TOOL'
  | 'WAITING_FOR_CONFIRMATION'
  | 'SPEAKING'
  | 'ERROR'
  | 'OFFLINE';

/**
 * Derives ONE JarvisState from the same event stream every other screen
 * already renders (see useJarvisSocket) — no separate state system, no
 * polling. Priority order matters: e.g. a pending confirmation always
 * wins over "processing" because the user needs to notice it.
 */
export function useJarvisState(
  events: JarvisEvent[],
  connectionStatus: ConnectionStatus,
  options: { hasPendingConfirmation: boolean; isRecording: boolean; isSpeaking: boolean }
): JarvisState {
  return useMemo(() => {
    if (connectionStatus !== 'connected') return 'OFFLINE';
    if (options.isRecording) return 'LISTENING';
    if (options.hasPendingConfirmation) return 'WAITING_FOR_CONFIRMATION';
    if (options.isSpeaking) return 'SPEAKING';

    // Look at the most recent task lifecycle event to infer what's
    // happening right now, walking backward until we hit a terminal one.
    for (let i = events.length - 1; i >= 0; i -= 1) {
      const event = events[i];
      switch (event.type) {
        case 'tool.started':
          return 'USING_TOOL';
        case 'task.failed':
          return 'ERROR';
        case 'task.completed':
        case 'confirmation.rejected':
          return 'IDLE';
        case 'task.planned':
        case 'task.started':
        case 'context.updated':
          return 'THINKING';
        case 'task.evaluating':
        case 'task.delta':
        case 'tool.completed':
          return 'PROCESSING';
        default:
          continue;
      }
    }
    return 'IDLE';
  }, [events, connectionStatus, options.hasPendingConfirmation, options.isRecording, options.isSpeaking]);
}
