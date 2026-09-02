# Jarvis — Android app

Expo (React Native) client. This is the Jarvis **interface only** — no AI
logic, no direct provider calls. Everything goes through the backend over
HTTPS (`src/api/client.ts`, `src/api/phase3Client.ts`) or WebSocket
(`src/hooks/useJarvisSocket.ts`). See `docs/ARCHITECTURE.md` at the repo
root.

## Setup

```bash
cd android
npm install
```

## Run

```bash
npm run android   # opens Metro + Android build (needs an emulator/device)
npm start         # Metro only, scan the QR code with Expo Go
```

On first launch, open **Settings** and point the app at your backend:

- **Backend HTTPS URL** — e.g. `http://10.0.2.2:8000` from the Android
  emulator (alias for the host machine), or your machine's LAN IP for a
  physical device.
- **Backend WebSocket URL** — same host, `/ws` path, `ws://` (or `wss://`
  once the backend is behind TLS).
- **API Token** — must match `JARVIS_API_TOKEN` in `backend/.env`.

Use "Test connection" to confirm the backend's `/health` is reachable
before relying on the WebSocket.

## Structure

```
src/
  theme/         centralized design tokens + JarvisState -> color mapping
  state/         useJarvisState — derives Jarvis's visual state from the
                 existing event stream (no separate state system)
  config/        persisted app settings (backend connection, TTS/voice/
                 privacy toggles)
  context/       SettingsProvider (React Context)
  api/           REST clients (Phase 1/2 + Phase 3) + the Event type
  tts/           expo-speech wrapper (real TTS, not device-verified)
  hooks/         useJarvisSocket, useChatMessages, usePendingConfirmation,
                 useAssistantSpeech, useAsyncData (shared fetch/loading/
                 error/refresh hook every Phase 3 screen uses)
  components/    JarvisCore (the voice button + 9-state visual identity),
                 ConnectionStatusBadge, ConfirmationDialog,
                 TaskProgressPanel, Card, StatusPill, EmptyState
  screens/       Home (command-center dashboard), Chat, Approvals, Audit,
                 Memory (search), Projects (+goals), Tasks, Wallet,
                 Business, Settings (sectioned: connection, voice,
                 privacy/24-7, autonomy, escalation contacts, system)
  navigation/    RootNavigator (stack)
```

## What's real vs. placeholder

**Real**: navigation, dark theme, WebSocket connection with reconnect,
live event stream rendering, the confirmation-dialog flow (approve/reject
round-trip to the backend), settings persistence, streaming assistant
text (`task.delta`), on-device text-to-speech (`expo-speech`), the entire
command-center dashboard and Approval/Audit/Memory/Projects/Tasks/Wallet/
Business screens (all backed by real REST endpoints against real
Postgres-backed services when the backend has them configured).

**Placeholder / not implemented**: the push-to-talk button does not
capture real audio — no wake word, VAD, or STT pipeline ships in this
build (see docs/PHASE_3.md). Holding `JarvisCore` sends a fixed demo
message so the full pipeline can be observed end to end; swapping in real
audio capture only changes `HomeScreen`'s `onPressIn`/`onPressOut`. The
Settings screen's "wake word" and "24/7 mode" toggles are visibly
disabled with an explanation, not silently omitted or faked as working.

## Verified in this repo

- `npx tsc --noEmit` — passes with zero errors.
- `npx expo-doctor` — 21/21 checks pass.
- `npx expo export --platform android` — bundles successfully (949
  modules as of Phase 3). Running on an actual emulator/device was **not**
  exercised in the sandbox this was built in (no Android SDK/emulator
  available) — that remains the first real-device verification step; see
  docs/PHASE_3.md's REAL/MOCKED/PARTIALLY_IMPLEMENTED/NOT_TESTED table.
