import React, { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react';
import { getToken, getClinicInfo } from '../lib/api';
import { useAuth } from './AuthContext';

const WebSocketContext = createContext(null);

export const WebSocketProvider = ({ children }) => {
  const { isAuthenticated, clinicId } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const listenersRef = useRef(new Map());
  const reconnectAttemptsRef = useRef(0);

  const getWsUrl = useCallback(() => {
    const token = getToken();
    const info = getClinicInfo();
    const cId = clinicId || info?.clinicId || "d3b07384-d113-46a6-a719-38cf89235d54";

    if (import.meta.env.VITE_WS_URL) {
      const base = import.meta.env.VITE_WS_URL.replace(/\/$/, "");
      return `${base}/ws/${cId}?token=${encodeURIComponent(token || "")}`;
    }

    const apiUrl = import.meta.env.VITE_API_URL || 
      (import.meta.env.PROD 
        ? 'https://clinic-os-production.up.railway.app/api/v1' 
        : 'http://localhost:8000/api/v1');

    let wsBase = apiUrl.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
    // If wsBase ends with /api/v1, keep or append /ws/{cId}
    if (wsBase.endsWith('/api/v1')) {
      return `${wsBase}/ws/${cId}?token=${encodeURIComponent(token || "")}`;
    } else {
      return `${wsBase.replace(/\/$/, "")}/ws/${cId}?token=${encodeURIComponent(token || "")}`;
    }
  }, [clinicId]);

  const addListener = useCallback((eventType, callback) => {
    if (!listenersRef.current.has(eventType)) {
      listenersRef.current.set(eventType, new Set());
    }
    listenersRef.current.get(eventType).add(callback);

    return () => {
      if (listenersRef.current.has(eventType)) {
        listenersRef.current.get(eventType).delete(callback);
      }
    };
  }, []);

  const dispatchEvent = useCallback((event, data) => {
    setLastEvent({ event, data, timestamp: Date.now() });

    // 1. Notify specific event listeners
    if (listenersRef.current.has(event)) {
      listenersRef.current.get(event).forEach((cb) => {
        try {
          cb(data);
        } catch (err) {
          console.error(`[WebSocket] Listener error for ${event}:`, err);
        }
      });
    }

    // 2. Notify wildcard listeners
    if (listenersRef.current.has('*')) {
      listenersRef.current.get('*').forEach((cb) => {
        try {
          cb({ event, data });
        } catch (err) {
          console.error(`[WebSocket] Wildcard listener error:`, err);
        }
      });
    }

    // 3. Dispatch standard DOM window event for decoupled sync
    try {
      window.dispatchEvent(
        new CustomEvent('bytelytic:ws_event', {
          detail: { event, data, timestamp: Date.now() },
        })
      );
      if (event === 'APPOINTMENT_ADDED' || event === 'APPOINTMENT_CREATED') {
        window.dispatchEvent(new CustomEvent('bytelytic:appointment_added', { detail: data }));
      } else if (event === 'APPOINTMENT_CANCELLED') {
        window.dispatchEvent(new CustomEvent('bytelytic:appointment_cancelled', { detail: data }));
      } else if (event === 'APPOINTMENT_UPDATED') {
        window.dispatchEvent(new CustomEvent('bytelytic:appointment_updated', { detail: data }));
      } else if (event === 'NEW_CALL') {
        window.dispatchEvent(new CustomEvent('bytelytic:new_call', { detail: data }));
      } else if (event === 'PRIOR_AUTH_CREATED' || event === 'PRIOR_AUTH_UPDATED') {
        window.dispatchEvent(new CustomEvent('bytelytic:prior_auth_updated', { detail: data }));
      } else if (event === 'OUTBOUND_CALL_TRIGGERED' || event === 'OUTBOUND_CALL_COMPLETED') {
        window.dispatchEvent(new CustomEvent('bytelytic:outbound_call_updated', { detail: data }));
      } else if (event === 'DASHBOARD_STATS_UPDATED') {
        window.dispatchEvent(new CustomEvent('bytelytic:dashboard_stats_updated', { detail: data }));
      }
    } catch (e) {
      // Ignore DOM dispatch issues in non-browser environments
    }
  }, []);

  const connect = useCallback(() => {
    if (!isAuthenticated) return;
    const token = getToken();
    if (!token) return;

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      const url = getWsUrl();
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;

        // Setup periodic heartbeat ping every 25s
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 25000);
      };

      ws.onmessage = (messageEvent) => {
        try {
          const raw = messageEvent.data;
          if (raw === 'pong' || raw === 'ping') return;

          const parsed = JSON.parse(raw);
          const eventName = parsed.event || parsed.type || 'UNKNOWN';
          const payloadData = parsed.data !== undefined ? parsed.data : parsed;

          dispatchEvent(eventName, payloadData);
        } catch (err) {
          // Non-JSON message, ignore
        }
      };

      ws.onclose = (closeEvent) => {
        setIsConnected(false);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

        // Do not reconnect if unauthorized or logged out
        if (closeEvent.code === 1008 || !getToken()) {
          return;
        }

        // Exponential backoff reconnect: 1s, 2s, 4s, up to max 15s
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 15000);
        reconnectAttemptsRef.current += 1;

        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      console.warn('[WebSocket] Connection initialization error:', e);
    }
  }, [isAuthenticated, getWsUrl, dispatchEvent]);

  useEffect(() => {
    if (isAuthenticated) {
      connect();
    } else {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
    }

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [isAuthenticated, connect]);

  const value = {
    isConnected,
    lastEvent,
    addListener,
    reconnect: connect,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    return {
      isConnected: false,
      lastEvent: null,
      addListener: () => () => {},
      reconnect: () => {},
    };
  }
  return context;
};

export default WebSocketContext;
