import { request } from '@umijs/max';

export interface ProcessInfo {
  pid: number;
  name: string;
  cpu_percent: number;
  mem_percent: number;
}

export interface AgentOut {
  agent_id: string;
  hostname: string;
  os: string;
  kernel: string;
  arch: string;
  public_ip: string;
  country_code: string;
  country: string;
  cpu_count: number;
  mem_total: number;
  cpu_percent: number;
  mem_percent: number;
  mem_used: number;
  process_count: number;
  load1: number;
  uptime_seconds: number;
  disk_total: number;
  disk_used: number;
  disk_percent: number;
  net_sent_rate: number;
  net_recv_rate: number;
  net_bytes_sent: number;
  net_bytes_recv: number;
  tcp_connections: number;
  tcp_established: number;
  top_processes: ProcessInfo[];
  first_seen: string;
  last_seen: string;
  online: boolean;
}

export interface Summary {
  total: number;
  online: number;
  offline: number;
  avg_cpu: number;
  avg_mem: number;
}

export interface MetricPoint {
  time: string;
  cpu_percent: number;
  mem_percent: number;
  mem_used: number;
  process_count: number;
  load1: number;
  disk_percent: number;
  net_sent_rate: number;
  net_recv_rate: number;
  tcp_connections: number;
}

export type WsMessage =
  | { type: 'snapshot'; summary: Summary; agents: AgentOut[] }
  | { type: 'agent'; data: AgentOut };

export async function fetchAgents() {
  return request<AgentOut[]>('/api/v1/agents', { method: 'GET' });
}

export async function fetchSummary() {
  return request<Summary>('/api/v1/summary', { method: 'GET' });
}

export async function fetchMetrics(agentId: string, minutes = 60) {
  return request<MetricPoint[]>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/metrics`,
    { method: 'GET', params: { minutes } },
  );
}

function dashboardWsUrl(): string {
  const token = localStorage.getItem('mon_token') ?? '';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // 与前端同源：开发环境经 dev proxy(8001)、生产经反向代理转发到后端
  return `${proto}//${window.location.host}/ws/dashboard?token=${encodeURIComponent(token)}`;
}

/** 订阅实时数据。自动断线重连；返回可用于关闭连接的控制器。 */
export function subscribeDashboard(
  onMessage: (msg: WsMessage) => void,
  onStatus?: (connected: boolean) => void,
): { close: () => void } {
  let ws: WebSocket | null = null;
  let closed = false;
  let retry = 0;
  let timer: number | undefined;

  const connect = () => {
    if (closed) return;
    ws = new WebSocket(dashboardWsUrl());

    ws.onopen = () => {
      retry = 0;
      onStatus?.(true);
    };
    ws.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data) as WsMessage);
      } catch {
        /* 忽略无法解析的消息 */
      }
    };
    ws.onclose = () => {
      onStatus?.(false);
      if (closed) return;
      retry = Math.min(retry + 1, 6);
      const delay = Math.min(1000 * 2 ** retry, 30000);
      timer = window.setTimeout(connect, delay);
    };
    ws.onerror = () => {
      ws?.close();
    };
  };

  connect();

  return {
    close: () => {
      closed = true;
      if (timer) window.clearTimeout(timer);
      ws?.close();
    },
  };
}
