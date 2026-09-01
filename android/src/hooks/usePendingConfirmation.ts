import { useMemo } from 'react';
import type { ConfirmationRequiredPayload, JarvisEvent } from '../api/events';

/**
 * The most recent confirmation.required event that hasn't yet been
 * resolved by a matching confirmation.approved/rejected. Null means no
 * dialog should be shown.
 */
export function usePendingConfirmation(events: JarvisEvent[]): ConfirmationRequiredPayload | null {
  return useMemo(() => {
    const resolvedIds = new Set(
      events
        .filter((e) => e.type === 'confirmation.approved' || e.type === 'confirmation.rejected')
        .map((e) => e.payload.confirmation_id as string)
    );

    for (let i = events.length - 1; i >= 0; i -= 1) {
      const event = events[i];
      if (event.type !== 'confirmation.required') continue;
      const payload = event.payload as unknown as ConfirmationRequiredPayload;
      if (!resolvedIds.has(payload.confirmation_id)) {
        return payload;
      }
    }
    return null;
  }, [events]);
}
