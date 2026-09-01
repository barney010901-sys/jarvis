import { useCallback, useEffect, useRef, useState } from 'react';
import type { JarvisEvent } from '../api/events';
import { useSettings } from '../context/SettingsContext';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';

const RECONNECT_DELAY_MS = 2000;
const MAX_EVENTS = 200;

/**
 * Owns the single WebSocket connection to the backend's /ws endpoint.
 * No AI logic — this only maintains the connection, forwards received
 * Events into React state, and exposes `sendUserMessage` to push a
 * user.message over the socket. See backend/app/ws/routes.py for the wire
 * protocol this must match.
 */
export function useJarvisSocket() {
  const { settings, loaded } = useSettings();
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [events, setEvents] = useState<JarvisEvent[]>([]);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!loaded || !settings.backendWsUrl) return;

    setStatus('connecting');
    const url = `${settings.backendWsUrl}?token=${encodeURIComponent(settings.apiToken)}`;
    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => {
      if (mountedRef.current) setStatus('connected');
    };

    socket.onmessage = (message) => {
      try {
        const event: JarvisEvent = JSON.parse(message.data);
        if (mountedRef.current) {
          setEvents((prev) => [...prev.slice(-(MAX_EVENTS - 1)), event]);
        }
      } catch {
        // Ignore malformed frames rather than crashing the UI.
      }
    };

    const scheduleReconnect = () => {
      if (!mountedRef.current) return;
      setStatus('disconnected');
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    socket.onerror = scheduleReconnect;
    socket.onclose = scheduleReconnect;
  }, [loaded, settings.backendWsUrl, settings.apiToken]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      socketRef.current?.close();
    };
  }, [connect]);

  const sendUserMessage = useCallback(
    (args: { sessionId: string; project?: string; text: string }) => {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) return false;
      socket.send(
        JSON.stringify({
          type: 'user.message',
          session_id: args.sessionId,
          project: args.project ?? 'default',
          text: args.text,
        })
      );
      return true;
    },
    []
  );

  const clearEvents = useCallback(() => setEvents([]), []);

  return { status, events, sendUserMessage, clearEvents };
}
