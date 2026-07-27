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
  net_errin: number;
  net_errout: number;
  net_dropin: number;
  net_dropout: number;
  net_errin_rate: number;
  net_errout_rate: number;
  net_dropin_rate: number;
  net_dropout_rate: number;
  tcp_retrans: number;
  tcp_retrans_rate: number;
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
  net_errin_rate: number;
  net_errout_rate: number;
  net_dropin_rate: number;
  net_dropout_rate: number;
  tcp_retrans_rate: number;
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

export interface MachinesDisplayPrefs {
  show_stat_cards: boolean;
  show_machine_cards: boolean;
}

export async function queryMachinesDisplayPrefs() {
  return request<MachinesDisplayPrefs>('/api/v1/machines-display-prefs', {
    method: 'GET',
  });
}

export async function updateMachinesDisplayPrefs(prefs: MachinesDisplayPrefs) {
  return request<MachinesDisplayPrefs>('/api/v1/machines-display-prefs', {
    method: 'PUT',
    data: prefs,
  });
}

function dashboardWsUrl(): string {
  const token = localStorage.getItem('mon_token') ?? '';
  // WS_BASE_URL 用于无法反代 WebSocket 的托管平台(如 Vercel)：直连后端。
  // 形如 wss://status-api.exploit-db.xyz(不带末尾斜杠)。
  const base = (process.env.WS_BASE_URL ?? '').replace(/\/+$/, '');
  if (base) {
    return `${base}/ws/dashboard?token=${encodeURIComponent(token)}`;
  }
  // 默认与前端同源：开发环境经 dev proxy(8001)、生产经反向代理转发到后端。
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
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
