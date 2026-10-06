// WebSocket hook with auto-reconnect.
// Staff pass their JWT (?token=), customers pass their order tokens (?orders=a,b). The socket
// reconnects whenever `query` changes so a customer starts receiving updates for a new order.
import { useEffect, useRef } from "react";
import { BACKEND_URL } from "./api";

export function useWs(onEvent, query = "") {
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    let ws;
    let closed = false;
    let timer;
    const connect = () => {
      const url = BACKEND_URL.replace(/^http/, "ws") + "/api/ws" + (query ? `?${query}` : "");
      ws = new WebSocket(url);
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          cb.current?.(msg.event, msg.data);
        } catch (_) {}
      };
      ws.onclose = (ev) => {
        // 4401 = rejected token; do not hammer the server.
        if (!closed && ev.code !== 4401) timer = setTimeout(connect, 2500);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, [query]);
}

// Query string for a staff connection.
export const staffWsQuery = () => {
  const token = localStorage.getItem("restos_token");
  return token ? `token=${encodeURIComponent(token)}` : "";
};
