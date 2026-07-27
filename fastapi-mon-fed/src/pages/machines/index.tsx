import { ArrowDownOutlined, ArrowUpOutlined, SettingOutlined } from '@ant-design/icons';
import { Line } from '@ant-design/plots';
import { PageContainer, StatisticCard } from '@ant-design/pro-components';
import {
  App,
  Badge,
  Button,
  Card,
  Col,
  Drawer,
  Empty,
  Progress,
  Row,
  Segmented,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
} from 'antd';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  type AgentOut,
  type MachinesDisplayPrefs,
  type MetricPoint,
  type ProcessInfo,
  type Summary,
  type WsMessage,
  fetchAgents,
  fetchMetrics,
  fetchSummary,
  queryMachinesDisplayPrefs,
  subscribeDashboard,
  updateMachinesDisplayPrefs,
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

/** 包/错误/丢包/重传速率，统一显示为 N/s */
function fmtPktRate(n: number | undefined): string {
  const v = n ?? 0;
  if (v >= 100) return `${Math.round(v)}/s`;
  return `${v.toFixed(1)}/s`;
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

function qualityWarn(n: number | undefined): string {
  return (n ?? 0) > 0 ? '#ff4d4f' : 'rgba(0,0,0,0.85)';
}

// 使用 flagcdn 图片渲染国旗（Windows 下 emoji 国旗无法正常显示）
const CountryFlag: React.FC<{ code?: string; country?: string; ip?: string }> = ({
  code,
  country,
  ip,
}) => {
  if (!code || code.length !== 2) return null;
  const lower = code.toLowerCase();
  return (
    <Tooltip title={`${country || code}${ip ? ` · ${ip}` : ''}`}>
      <img
        src={`https://flagcdn.com/24x18/${lower}.png`}
        srcSet={`https://flagcdn.com/48x36/${lower}.png 2x`}
        width={24}
        height={18}
        alt={code}
        style={{ borderRadius: 2, boxShadow: '0 0 1px rgba(0,0,0,0.35)', verticalAlign: 'middle' }}
      />
    </Tooltip>
  );
};

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
        <Space size={6}>
          <CountryFlag
            code={agent.country_code}
            country={agent.country}
            ip={agent.public_ip}
          />
          <Tag color={agent.online ? 'green' : 'red'} style={{ marginInlineEnd: 0 }}>
            {agent.online ? '在线' : '离线'}
          </Tag>
        </Space>
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
          <Tooltip title={`入 ${fmtPktRate(agent.net_dropin_rate)} · 出 ${fmtPktRate(agent.net_dropout_rate)}`}>
            丢包{' '}
            <b style={{ color: qualityWarn((agent.net_dropin_rate ?? 0) + (agent.net_dropout_rate ?? 0)) }}>
              {fmtPktRate((agent.net_dropin_rate ?? 0) + (agent.net_dropout_rate ?? 0))}
            </b>
          </Tooltip>
        </Col>
        <Col span={8}>
          <Tooltip title={`入 ${fmtPktRate(agent.net_errin_rate)} · 出 ${fmtPktRate(agent.net_errout_rate)}`}>
            错误{' '}
            <b style={{ color: qualityWarn((agent.net_errin_rate ?? 0) + (agent.net_errout_rate ?? 0)) }}>
              {fmtPktRate((agent.net_errin_rate ?? 0) + (agent.net_errout_rate ?? 0))}
            </b>
          </Tooltip>
        </Col>
        <Col span={8}>
          <Tooltip title={`累计重传 ${agent.tcp_retrans ?? 0}`}>
            重传{' '}
            <b style={{ color: qualityWarn(agent.tcp_retrans_rate) }}>
              {fmtPktRate(agent.tcp_retrans_rate)}
            </b>
          </Tooltip>
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
  const { message } = App.useApp();
  const [agents, setAgents] = useState<Record<string, AgentOut>>({});
  const [summary, setSummary] = useState<Summary>({
    total: 0,
    online: 0,
    offline: 0,
    avg_cpu: 0,
    avg_mem: 0,
  });
  const [connected, setConnected] = useState(false);
  const [metricField, setMetricField] = useState<'cpu' | 'mem' | 'disk' | 'net' | 'quality' | 'tcp'>('cpu');
  const [selected, setSelected] = useState<AgentOut | null>(null);
  const [history, setHistory] = useState<MetricPoint[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [displayPrefs, setDisplayPrefs] = useState<MachinesDisplayPrefs>({
    show_stat_cards: true,
    show_machine_cards: true,
    hidden_agent_ids: [],
  });
  const [prefsSaving, setPrefsSaving] = useState(false);
  type MetricField = 'cpu' | 'mem' | 'disk' | 'net' | 'quality' | 'tcp';

  const subRef = useRef<{ close: () => void } | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const [list, sum] = await Promise.all([fetchAgents(), fetchSummary()]);
        if (cancelled) return;
        const map: Record<string, AgentOut> = {};
        for (const a of list) map[a.agent_id] = a;
        setAgents(map);
        setSummary(sum);
      } catch {
        /* WS 仍会尝试拉取 */
      }
      try {
        const prefs = await queryMachinesDisplayPrefs();
        if (!cancelled) setDisplayPrefs(prefs);
      } catch {
        /* 使用默认显示偏好 */
      }
    })();

    const sub = subscribeDashboard(
      (msg: WsMessage) => {
        if (msg.type === 'snapshot') {
          setSummary(msg.summary);
          // 空 snapshot 不覆盖已有列表，避免异常空帧把 UI 清空
          if (msg.agents.length === 0) {
            setAgents((prev) => (Object.keys(prev).length > 0 ? prev : {}));
            return;
          }
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
    return () => {
      cancelled = true;
      sub.close();
    };
  }, []);

  const saveDisplayPrefs = async (next: MachinesDisplayPrefs) => {
    const prev = displayPrefs;
    setDisplayPrefs(next);
    setPrefsSaving(true);
    try {
      const saved = await updateMachinesDisplayPrefs(next);
      setDisplayPrefs(saved);
    } catch {
      setDisplayPrefs(prev);
      message.error('保存显示设置失败，请重试');
    } finally {
      setPrefsSaving(false);
    }
  };
  const agentList = useMemo(
    () => Object.values(agents).sort((a, b) => a.hostname.localeCompare(b.hostname)),
    [agents],
  );

  const hiddenSet = useMemo(
    () => new Set(displayPrefs.hidden_agent_ids ?? []),
    [displayPrefs.hidden_agent_ids],
  );

  const visibleAgentList = useMemo(
    () => agentList.filter((a) => !hiddenSet.has(a.agent_id)),
    [agentList, hiddenSet],
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

  // 统一坐标轴与 tooltip 的数值单位
  const valueFmt = (v: number) =>
    isPercent
      ? `${v}%`
      : metricField === 'net'
        ? fmtRate(v)
        : metricField === 'quality'
          ? fmtPktRate(v)
          : `${v}`;

  // net / quality 为多序列；其余为单序列
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
    if (metricField === 'quality') {
      return history.flatMap((p) => {
        const t = new Date(p.time).toLocaleTimeString('zh-CN');
        return [
          { time: t, value: (p.net_dropin_rate ?? 0) + (p.net_dropout_rate ?? 0), series: '丢包' },
          { time: t, value: (p.net_errin_rate ?? 0) + (p.net_errout_rate ?? 0), series: '错误' },
          { time: t, value: p.tcp_retrans_rate ?? 0, series: '重传' },
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
          <Button
            key="display-settings"
            icon={<SettingOutlined />}
            onClick={() => setSettingsOpen(true)}
          >
            显示设置
          </Button>,
        ],
      }}
    >
      {displayPrefs.show_stat_cards && (
        <div
          style={{
            display: 'flex',
            gap: 16,
            flexWrap: 'wrap',
            marginBottom: 16,
          }}
        >
          <StatisticCard
            bordered
            style={{ flex: '1 1 150px' }}
            statistic={{ title: '机器总数', value: summary.total }}
          />
          <StatisticCard
            bordered
            style={{ flex: '1 1 150px' }}
            statistic={{ title: '在线', value: summary.online, valueStyle: { color: '#52c41a' } }}
          />
          <StatisticCard
            bordered
            style={{ flex: '1 1 150px' }}
            statistic={{
              title: '离线',
              value: summary.offline,
              valueStyle: { color: summary.offline ? '#ff4d4f' : undefined },
            }}
          />
        </div>
      )}

      {displayPrefs.show_machine_cards &&
        (agentList.length === 0 ? (
          <Empty description="暂无机器上报，请启动客户端(agent)后稍候" style={{ padding: '60px 0' }} />
        ) : visibleAgentList.length === 0 ? (
          <Empty description="所有机器卡片已隐藏，可在「管理页 → 主机管理」中重新开启" style={{ padding: '60px 0' }} />
        ) : (
          <Row gutter={[16, 16]}>
            {visibleAgentList.map((a) => (
              <Col key={a.agent_id} xs={24} sm={12} md={8} xl={6}>
                <MachineCard agent={a} onClick={() => openDetail(a)} />
              </Col>
            ))}
          </Row>
        ))}

      <Drawer
        width={400}
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        title="显示设置"
        destroyOnHidden
      >
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>显示统计卡片（机器总数/在线/离线）</span>
            <Switch
              checked={displayPrefs.show_stat_cards}
              loading={prefsSaving}
              onChange={(checked) =>
                saveDisplayPrefs({ ...displayPrefs, show_stat_cards: checked })
              }
            />
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>显示机器卡片网格</span>
            <Switch
              checked={displayPrefs.show_machine_cards}
              loading={prefsSaving}
              onChange={(checked) =>
                saveDisplayPrefs({ ...displayPrefs, show_machine_cards: checked })
              }
            />
          </div>
        </Space>
      </Drawer>

      <Drawer
        width={720}
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? `${selected.hostname} · 详情` : ''}
        destroyOnHidden
      >
        {selected && (
          <>
            <div
              style={{
                display: 'flex',
                gap: 12,
                flexWrap: 'wrap',
                marginBottom: 16,
              }}
            >
              <StatisticCard
                bordered
                style={{ flex: '1 1 120px' }}
                statistic={{ title: 'CPU', value: selected.cpu_percent, suffix: '%' }}
              />
              <StatisticCard
                bordered
                style={{ flex: '1 1 120px' }}
                statistic={{ title: '内存', value: selected.mem_percent, suffix: '%' }}
              />
              <StatisticCard
                bordered
                style={{ flex: '1 1 120px' }}
                statistic={{ title: '磁盘', value: selected.disk_percent, suffix: '%' }}
              />
              <StatisticCard
                bordered
                style={{ flex: '1 1 120px' }}
                statistic={{ title: '进程数', value: selected.process_count }}
              />
              <StatisticCard
                bordered
                style={{ flex: '1 1 120px' }}
                statistic={{ title: 'TCP 连接', value: selected.tcp_connections }}
              />
            </div>

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
                <Col span={12}>
                  丢包速率：
                  <span style={{ color: qualityWarn((selected.net_dropin_rate ?? 0) + (selected.net_dropout_rate ?? 0)) }}>
                    {fmtPktRate((selected.net_dropin_rate ?? 0) + (selected.net_dropout_rate ?? 0))}
                  </span>
                  （入 {selected.net_dropin ?? 0} / 出 {selected.net_dropout ?? 0}）
                </Col>
                <Col span={12}>
                  错误速率：
                  <span style={{ color: qualityWarn((selected.net_errin_rate ?? 0) + (selected.net_errout_rate ?? 0)) }}>
                    {fmtPktRate((selected.net_errin_rate ?? 0) + (selected.net_errout_rate ?? 0))}
                  </span>
                  （入 {selected.net_errin ?? 0} / 出 {selected.net_errout ?? 0}）
                </Col>
                <Col span={12}>
                  TCP 重传：
                  <span style={{ color: qualityWarn(selected.tcp_retrans_rate) }}>
                    {fmtPktRate(selected.tcp_retrans_rate)}
                  </span>
                  （累计 {selected.tcp_retrans ?? 0}）
                </Col>
                <Col span={12}>TCP(ESTAB)：{selected.tcp_established}</Col>
                <Col span={12}>运行时长：{fmtUptime(selected.uptime_seconds)}</Col>
                <Col span={12}>
                  <Space size={6}>
                    外网 IP：{selected.public_ip || '-'}
                    <CountryFlag
                      code={selected.country_code}
                      country={selected.country}
                      ip={selected.public_ip}
                    />
                  </Space>
                </Col>
                <Col span={12}>
                  国家/地区：{selected.country || selected.country_code || '-'}
                </Col>
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
                  { label: '网络质量', value: 'quality' },
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
                  legend={
                    metricField === 'net' || metricField === 'quality'
                      ? { color: { position: 'top' } }
                      : false
                  }
                  axis={{ y: { labelFormatter: valueFmt } }}
                  tooltip={{ channel: 'y', valueFormatter: valueFmt }}
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
