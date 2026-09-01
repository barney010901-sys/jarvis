# Jarvis — Android app

Expo (React Native) client. This is the Jarvis **interface only** — no AI
logic, no direct provider calls. Everything goes through the backend over
HTTPS (`src/api/client.ts`) or WebSocket (`src/hooks/useJarvisSocket.ts`).
See `docs/ARCHITECTURE.md` at the repo root.

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
  theme/         centralized design tokens (dark futuristic palette)
  config/        persisted backend connection settings
  context/       SettingsProvider (React Context)
  api/           REST client + the Event type mirroring the backend
  hooks/         useJarvisSocket (WS connection), useChatMessages,
                 usePendingConfirmation
  components/    VoiceButton, ConnectionStatusBadge, ConfirmationDialog,
                 TaskProgressPanel
  screens/       HomeScreen, ChatScreen, SettingsScreen
  navigation/    RootNavigator (stack)
```

## What's real vs. placeholder in Phase 1

- Real: navigation, dark theme, WebSocket connection with reconnect,
  live event stream rendering (task/tool status), the confirmation-dialog
  flow (approve/reject actually round-trip to the backend), settings
  persistence.
- Placeholder: the voice button does not capture real audio yet (no STT
  upload) — holding it sends a fixed demo message so the full event
  pipeline can be observed. Wiring real audio capture is a Phase 2 change
  to `HomeScreen`'s `onPressIn`/`onPressOut` handlers, not to any other
  part of the app. Streaming assistant text currently renders the full
  response once `task.completed` arrives, since the backend doesn't
  stream token-by-token yet either (see `agent/README.md`).

## Verified in this repo

- `npx tsc --noEmit` — passes with zero errors.
- `npx expo-doctor` — 21/21 checks pass.
- `npx expo export --platform android` — bundles successfully (931
  modules). Running on an actual emulator/device was not exercised in the
  sandbox this was built in — do that as the first step of Phase 2.
