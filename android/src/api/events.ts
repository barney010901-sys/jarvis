/**
 * Mirrors backend/app/events/models.py exactly. If the backend event
 * vocabulary changes, update both places together.
 */
export type EventType =
  | 'user.message'
  | 'voice.transcription.completed'
  | 'task.created'
  | 'task.planned'
  | 'task.started'
  | 'tool.started'
  | 'tool.completed'
  | 'confirmation.required'
  | 'confirmation.approved'
  | 'confirmation.rejected'
  | 'task.failed'
  | 'task.completed'
  // --- Phase 2 additions (backend/app/events/models.py) ---
  | 'context.updated'
  | 'task.evaluating'
  | 'knowledge.created'
  | 'knowledge.updated'
  | 'interest.detected'
  | 'suggestion.created'
  | 'task.delta';

export type JarvisEvent = {
  id: string;
  type: EventType;
  timestamp: string;
  task_id: string | null;
  correlation_id: string | null;
  payload: Record<string, unknown>;
};

export type ConfirmationRequiredPayload = {
  confirmation_id: string;
  tool_name: string;
  description: string;
  details: Record<string, unknown>;
};
