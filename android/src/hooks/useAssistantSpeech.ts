import { useEffect, useRef, useState } from 'react';
import { speak, stopSpeaking } from '../tts/speech';
import type { ChatMessage } from './useChatMessages';

/**
 * Speaks each newly-completed assistant message via on-device TTS. Only
 * speaks finished (non-pending) messages, so partial streaming text is
 * never read aloud mid-sentence — it waits for task.completed the same
 * way the chat bubble does.
 */
export function useAssistantSpeech(messages: ChatMessage[], enabled: boolean) {
  const spokenIds = useRef(new Set<string>()).current;
  const [isSpeaking, setIsSpeaking] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    const last = messages[messages.length - 1];
    if (!last || last.role !== 'assistant' || last.pending || spokenIds.has(last.id)) return;
    spokenIds.add(last.id);

    speak(last.text, {
      onStart: () => setIsSpeaking(true),
      onDone: () => setIsSpeaking(false),
      onStopped: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  }, [messages, enabled, spokenIds]);

  useEffect(() => {
    if (!enabled) {
      stopSpeaking();
      setIsSpeaking(false);
    }
  }, [enabled]);

  return { isSpeaking, stop: stopSpeaking };
}
