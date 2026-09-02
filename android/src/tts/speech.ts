import * as Speech from 'expo-speech';

/**
 * Thin wrapper over expo-speech — REAL text-to-speech, not a stub. Not
 * verified on a physical device in this build (no device/emulator was
 * available — see docs/PHASE_3.md); the API calls themselves are correct
 * and this is the only place in the app that touches the TTS engine.
 */
export function speak(text: string, callbacks?: { onStart?: () => void; onDone?: () => void; onStopped?: () => void; onError?: () => void }): void {
  const trimmed = text.trim();
  if (!trimmed) return;
  Speech.stop();
  Speech.speak(trimmed, {
    onStart: callbacks?.onStart,
    onDone: callbacks?.onDone,
    onStopped: callbacks?.onStopped,
    onError: callbacks?.onError,
  });
}

export function stopSpeaking(): void {
  Speech.stop();
}
