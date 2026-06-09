import AsyncStorage from '@react-native-async-storage/async-storage';
import { ANALYTICS_URL } from './client';

type WSEvent = { event: string; data?: any };
type EventHandler = (data: any) => void;

class SleepSenseWS {
  private ws: WebSocket | null = null;
  private handlers: Map<string, EventHandler[]> = new Map();

  async connect(): Promise<void> {
    if (this.ws) return;
    const token = await AsyncStorage.getItem('access_token');
    if (!token) return;
    const url = ANALYTICS_URL.replace(/^http/, 'ws') + '/ws';
    try {
      this.ws = new WebSocket(url);
      this.ws.onopen = () => {
        // Send auth as the first message — keeps the token out of server logs and URL history
        this.ws?.send(JSON.stringify({ token }));
      };
      this.ws.onmessage = (e) => {
        try {
          const msg: WSEvent = JSON.parse(e.data);
          if (msg.event === 'ping') return;
          (this.handlers.get(msg.event) ?? []).forEach(h => h(msg.data));
        } catch {}
      };
      this.ws.onerror = (err) => {
        console.warn('[SleepSenseWS] error', err);
      };
      this.ws.onclose = () => { this.ws = null; };
    } catch (err) {
      console.warn('[SleepSenseWS] connect failed', err);
    }
  }

  on(event: string, handler: EventHandler): () => void {
    const list = this.handlers.get(event) ?? [];
    list.push(handler);
    this.handlers.set(event, list);
    return () => {
      this.handlers.set(event, (this.handlers.get(event) ?? []).filter(h => h !== handler));
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
    this.handlers.clear();
  }
}

export const sleepSenseWS = new SleepSenseWS();
