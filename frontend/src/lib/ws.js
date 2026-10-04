import { useEffect, useRef } from "react";
import { BACKEND_URL } from "./api";

export function useWs(onEvent) {
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    let ws;
    let closed = false;
    let timer;
    const connect = () => {
      const url = BACKEND_URL.replace(/^http/, "ws") + "/api/ws";
      ws = new WebSocket(url);
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          cb.current?.(msg.event, msg.data);
        } catch (_) {}
      };
      ws.onclose = () => {
        if (!closed) timer = setTimeout(connect, 2500);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);
}
