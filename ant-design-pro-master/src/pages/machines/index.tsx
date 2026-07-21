import { ArrowDownOutlined, ArrowUpOutlined } from '@ant-design/icons';
import { Column, Line } from '@ant-design/plots';
import { PageContainer, ProCard, StatisticCard } from '@ant-design/pro-components';
import {
  Badge,
  Card,
  Col,
  Drawer,
  Empty,
  Progress,
  Row,
  Segmented,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
} from 'antd';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  type AgentOut,
  type MetricPoint,
  type ProcessInfo,
  type Summary,
  type WsMessage,
  fetchMetrics,
  subscribeDashboard,
} from '@/services/mon';

function fmtBytes(n: number): string {
  if (!n) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(n) / Math.log(1024));
  return `${(n / 1024 ** i).toFixed(1)} ${units[i]}`;
}

function fmtRate(n: number): string {
  return `${fmtBytes(n)}/s`;
}

function fmtUptime(s: number): string {
  if (!s) return '-';
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}天 ${h}小时`;
  if (h > 0) return `${h}小时 ${m}分`;
  return `${m}分`;
}

function usageColor(p: number): string {
  if (p >= 90) return '#ff4d4f';
  if (p >= 70) return '#faad14';
  return '#52c41a';
}

const MachineCard: React.FC<{
  agent: AgentOut;
  onClick: () => void;
}> = ({ agent, onClick }) => {
  return (
    <Card
      hoverable
      onClick={onClick}
      styles={{ body: { padding: 18 } }}
      title={
        <Space>
          <Badge status={agent.online ? 'success' : 'error'} />
          <span style={{ fontWeight: 600 }}>{agent.hostname}</span>
        </Space>
      }
      extra={
        <Tag color={agent.online ? 'green' : 'red'}>
          {agent.online ? '在线' : '离线'}
        </Tag>
      }
    >
      <div style={{ color: '#8c8c8c', fontSize: 12, marginBottom: 12 }}>
        {agent.os} · {agent.arch} · {agent.cpu_count} 核
      </div>

      <div style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span>CPU</span>
          <span>{agent.cpu_percent.toFixed(1)}%</span>
        </div>
        <Progress
          percent={Math.round(agent.cpu_percent)}
          showInfo={false}
          strokeColor={usageColor(agent.cpu_percent)}
        />
      </div>

      <div style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span>内存 ({fmtBytes(agent.mem_total)})</span>
          <span>{agent.mem_percent.toFixed(1)}%</span>
        </div>
        <Progress
          percent={Math.round(agent.mem_percent)}
          showInfo={false}
          strokeColor={usageColor(agent.mem_percent)}
        />
      </div>

      <div style={{ marginBottom: 4 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
          <span>磁盘 ({fmtBytes(agent.disk_total)})</span>
          <span>{agent.disk_percent.toFixed(1)}%</span>
        </div>
        <Progress
          percent={Math.round(agent.disk_percent)}
          showInfo={false}
          strokeColor={usageColor(agent.disk_percent)}
        />
      </div>

      <Row style={{ marginTop: 12, color: '#8c8c8c', fontSize: 12 }} gutter={[8, 6]}>
        <Col span={12}>
          <ArrowUpOutlined style={{ color: '#52c41a' }} />{' '}
          <b style={{ color: 'rgba(0,0,0,0.85)' }}>{fmtRate(agent.net_sent_rate)}</b>
        </Col>
        <Col span={12}>
          <ArrowDownOutlined style={{ color: '#4f8cff' }} />{' '}
          <b style={{ color: 'rgba(0,0,0,0.85)' }}>{fmtRate(agent.net_recv_rate)}</b>
        </Col>
        <Col span={8}>
          进程 <b style={{ color: 'rgba(0,0,0,0.85)' }}>{agent.process_count}</b>
        </Col>
        <Col span={8}>
          TCP <b style={{ color: 'rgba(0,0,0,0.85)' }}>{agent.tcp_connections}</b>
        </Col>
        <Col span={8}>
          <Tooltip title={`内核 ${agent.kernel} · 运行 ${fmtUptime(agent.uptime_seconds)}`}>
            负载 <b style={{ color: 'rgba(0,0,0,0.85)' }}>{agent.load1.toFixed(2)}</b>
          </Tooltip>
        </Col>
      </Row>
    </Card>
  );
};

const Machines: React.FC = () => {
  const [agents, setAgents] = useState<Record<string, AgentOut>>({});
  const [summary, setSummary] = useState<Summary>({
    total: 0,
    online: 0,
    offline: 0,
    avg_cpu: 0,
    avg_mem: 0,
  });
  const [connected, setConnected] = useState(false);
  const [metricField, setMetricField] = useState<'cpu' | 'mem' | 'disk' | 'net' | 'tcp'>('cpu');

  const [selected, setSelected] = useState<AgentOut | null>(null);
  const [history, setHistory] = useState<MetricPoint[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  type MetricField = 'cpu' | 'mem' | 'disk' | 'net' | 'tcp';

  const subRef = useRef<{ close: () => void } | null>(null);

  useEffect(() => {
    const sub = subscribeDashboard(
      (msg: WsMessage) => {
        if (msg.type === 'snapshot') {
          setSummary(msg.summary);
          const map: Record<string, AgentOut> = {};
          for (const a of msg.agents) map[a.agent_id] = a;
          setAgents(map);
        } else if (msg.type === 'agent') {
          setAgents((prev) => ({ ...prev, [msg.data.agent_id]: msg.data }));
        }
      },
      (ok) => setConnected(ok),
    );
    subRef.current = sub;
    return () => sub.close();
  }, []);

  const agentList = useMemo(
    () => Object.values(agents).sort((a, b) => a.hostname.localeCompare(b.hostname)),
    [agents],
  );

  const overviewData = useMemo(
    () =>
      agentList.flatMap((a) => [
        { host: a.hostname, type: 'CPU', value: Number(a.cpu_percent.toFixed(1)) },
        { host: a.hostname, type: '内存', value: Number(a.mem_percent.toFixed(1)) },
        { host: a.hostname, type: '磁盘', value: Number(a.disk_percent.toFixed(1)) },
      ]),
    [agentList],
  );

  const openDetail = async (agent: AgentOut) => {
    setSelected(agent);
    setHistoryLoading(true);
    try {
      const data = await fetchMetrics(agent.agent_id, 60);
      setHistory(data);
    } finally {
      setHistoryLoading(false);
    }
  };

  const isPercent = metricField === 'cpu' || metricField === 'mem' || metricField === 'disk';

  // net 为双序列(上行/下行)；其余为单序列
  const historyData = useMemo(() => {
    if (metricField === 'net') {
      return history.flatMap((p) => {
        const t = new Date(p.time).toLocaleTimeString('zh-CN');
        return [
          { time: t, value: p.net_sent_rate, series: '上行' },
          { time: t, value: p.net_recv_rate, series: '下行' },
        ];
      });
    }
    const pick = (p: MetricPoint) => {
      switch (metricField) {
        case 'cpu':
          return p.cpu_percent;
        case 'mem':
          return p.mem_percent;
        case 'disk':
          return p.disk_percent;
        case 'tcp':
          return p.tcp_connections;
        default:
          return 0;
      }
    };
    return history.map((p) => ({
      time: new Date(p.time).toLocaleTimeString('zh-CN'),
      value: pick(p),
      series: '值',
    }));
  }, [history, metricField]);

  return (
    <PageContainer
      header={{
        title: '机器监控',
        extra: [
          <Badge
            key="conn"
            status={connected ? 'processing' : 'default'}
            text={connected ? '实时连接' : '连接中…'}
          />,
        ],
      }}
    >
      <StatisticCard.Group direction="row" style={{ marginBottom: 16 }}>
        <StatisticCard statistic={{ title: '机器总数', value: summary.total }} />
        <StatisticCard.Divider />
        <StatisticCard
          statistic={{ title: '在线', value: summary.online, valueStyle: { color: '#52c41a' } }}
        />
        <StatisticCard
          statistic={{
            title: '离线',
            value: summary.offline,
            valueStyle: { color: summary.offline ? '#ff4d4f' : undefined },
          }}
        />
        <StatisticCard.Divider />
        <StatisticCard statistic={{ title: '平均 CPU', value: summary.avg_cpu, suffix: '%' }} />
        <StatisticCard statistic={{ title: '平均内存', value: summary.avg_mem, suffix: '%' }} />
      </StatisticCard.Group>

      <ProCard title="各机器资源使用率总览" style={{ marginBottom: 16 }} bordered>
        {agentList.length === 0 ? (
          <Empty description="暂无机器上报，请启动客户端(agent)后稍候" />
        ) : (
          <Column
            data={overviewData}
            xField="host"
            yField="value"
            colorField="type"
            group
            height={300}
            axis={{ y: { labelFormatter: (v: number) => `${v}%` } }}
            scale={{ y: { domainMax: 100 } }}
            legend={{ color: { position: 'top' } }}
          />
        )}
      </ProCard>

      {agentList.length === 0 ? null : (
        <Row gutter={[16, 16]}>
          {agentList.map((a) => (
            <Col key={a.agent_id} xs={24} sm={12} md={8} xl={6}>
              <MachineCard agent={a} onClick={() => openDetail(a)} />
            </Col>
          ))}
        </Row>
      )}

      <Drawer
        width={720}
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `${selected.hostname} · 详情` : ''}
        destroyOnHidden
      >
        {selected && (
          <>
            <StatisticCard.Group direction="row" style={{ marginBottom: 16 }} wrap>
              <StatisticCard statistic={{ title: 'CPU', value: selected.cpu_percent, suffix: '%' }} />
              <StatisticCard statistic={{ title: '内存', value: selected.mem_percent, suffix: '%' }} />
              <StatisticCard statistic={{ title: '磁盘', value: selected.disk_percent, suffix: '%' }} />
              <StatisticCard statistic={{ title: '进程数', value: selected.process_count }} />
              <StatisticCard
                statistic={{ title: 'TCP 连接', value: selected.tcp_connections }}
              />
            </StatisticCard.Group>

            <Card size="small" style={{ marginBottom: 16 }}>
              <Row gutter={[8, 8]} style={{ fontSize: 13 }}>
                <Col span={12}>系统：{selected.os} {selected.arch}</Col>
                <Col span={12}>内核：{selected.kernel || '-'}</Col>
                <Col span={12}>CPU 核心：{selected.cpu_count}</Col>
                <Col span={12}>内存总量：{fmtBytes(selected.mem_total)}</Col>
                <Col span={12}>磁盘总量：{fmtBytes(selected.disk_total)}</Col>
                <Col span={12}>磁盘已用：{fmtBytes(selected.disk_used)}</Col>
                <Col span={12}>网络 ↑：{fmtRate(selected.net_sent_rate)}</Col>
                <Col span={12}>网络 ↓：{fmtRate(selected.net_recv_rate)}</Col>
                <Col span={12}>TCP(ESTAB)：{selected.tcp_established}</Col>
                <Col span={12}>运行时长：{fmtUptime(selected.uptime_seconds)}</Col>
                <Col span={24}>Agent ID：{selected.agent_id}</Col>
              </Row>
            </Card>

            <div style={{ marginBottom: 12 }}>
              <Segmented
                value={metricField}
                onChange={(v) => setMetricField(v as MetricField)}
                options={[
                  { label: 'CPU', value: 'cpu' },
                  { label: '内存', value: 'mem' },
                  { label: '磁盘', value: 'disk' },
                  { label: '网络', value: 'net' },
                  { label: 'TCP', value: 'tcp' },
                ]}
              />
            </div>

            <Spin spinning={historyLoading}>
              {historyData.length === 0 ? (
                <Empty description="暂无历史数据" />
              ) : (
                <Line
                  data={historyData}
                  xField="time"
                  yField="value"
                  colorField="series"
                  height={260}
                  smooth
                  legend={metricField === 'net' ? { color: { position: 'top' } } : false}
                  axis={{
                    y: {
                      labelFormatter: (v: number) =>
                        isPercent ? `${v}%` : metricField === 'net' ? fmtRate(v) : `${v}`,
                    },
                  }}
                  scale={isPercent ? { y: { domainMax: 100, domainMin: 0 } } : {}}
                  style={{ lineWidth: 2 }}
                />
              )}
            </Spin>

            <div style={{ marginTop: 20, marginBottom: 8, fontWeight: 600 }}>
              Top 进程（按 CPU）
            </div>
            <Table<ProcessInfo>
              size="small"
              rowKey="pid"
              pagination={false}
              dataSource={selected.top_processes}
              locale={{ emptyText: '暂无数据' }}
              columns={[
                { title: 'PID', dataIndex: 'pid', width: 90 },
                { title: '进程', dataIndex: 'name', ellipsis: true },
                {
                  title: 'CPU %',
                  dataIndex: 'cpu_percent',
                  width: 100,
                  render: (v: number) => `${v.toFixed(1)}%`,
                  sorter: (a, b) => a.cpu_percent - b.cpu_percent,
                },
                {
                  title: '内存 %',
                  dataIndex: 'mem_percent',
                  width: 100,
                  render: (v: number) => `${v.toFixed(1)}%`,
                },
              ]}
            />
          </>
        )}
      </Drawer>
    </PageContainer>
  );
};

export default Machines;
