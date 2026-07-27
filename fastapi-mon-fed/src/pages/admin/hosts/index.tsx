import { DeleteOutlined } from '@ant-design/icons';
import { PageContainer } from '@ant-design/pro-components';
import {
  App,
  Badge,
  Button,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  type AgentOut,
  type MachinesDisplayPrefs,
  type WsMessage,
  deleteAgent,
  fetchAgents,
  queryMachinesDisplayPrefs,
  subscribeDashboard,
  updateMachinesDisplayPrefs,
} from '@/services/mon';

const AdminHosts: React.FC = () => {
  const { message } = App.useApp();
  const [agents, setAgents] = useState<Record<string, AgentOut>>({});
  const [displayPrefs, setDisplayPrefs] = useState<MachinesDisplayPrefs>({
    show_stat_cards: true,
    show_machine_cards: true,
    hidden_agent_ids: [],
  });
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const subRef = useRef<{ close: () => void } | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const list = await fetchAgents();
        if (cancelled) return;
        const map: Record<string, AgentOut> = {};
        for (const a of list) map[a.agent_id] = a;
        setAgents(map);
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

    const sub = subscribeDashboard((msg: WsMessage) => {
      if (msg.type === 'snapshot') {
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
    });
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

  const hiddenSet = useMemo(
    () => new Set(displayPrefs.hidden_agent_ids ?? []),
    [displayPrefs.hidden_agent_ids],
  );

  const agentList = useMemo(
    () => Object.values(agents).sort((a, b) => a.hostname.localeCompare(b.hostname)),
    [agents],
  );

  const toggleAgentHidden = (agentId: string, visible: boolean) => {
    const current = displayPrefs.hidden_agent_ids ?? [];
    const nextHidden = visible
      ? current.filter((id) => id !== agentId)
      : [...new Set([...current, agentId])];
    void saveDisplayPrefs({ ...displayPrefs, hidden_agent_ids: nextHidden });
  };

  const handleDelete = async (agentId: string) => {
    setDeletingId(agentId);
    try {
      await deleteAgent(agentId);
      setAgents((prev) => {
        const next = { ...prev };
        delete next[agentId];
        return next;
      });
      const current = displayPrefs.hidden_agent_ids ?? [];
      if (current.includes(agentId)) {
        const nextHidden = current.filter((id) => id !== agentId);
        void saveDisplayPrefs({ ...displayPrefs, hidden_agent_ids: nextHidden });
      }
      message.success('主机记录已删除');
    } catch {
      message.error('删除失败，请重试');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <PageContainer
      header={{
        title: '主机管理',
        subTitle: '管理监控主机记录与卡片显示',
      }}
    >
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        关闭「显示卡片」后该主机卡片不会出现在机器监控网格中（统计仍计入）。删除记录将清除该主机的历史指标数据；若
        Agent 仍在运行，下次上报时会重新注册。
      </Typography.Paragraph>

      <Table<AgentOut>
        rowKey="agent_id"
        dataSource={agentList}
        pagination={false}
        locale={{ emptyText: '暂无主机' }}
        columns={[
          {
            title: '主机名',
            dataIndex: 'hostname',
            ellipsis: true,
            render: (hostname: string, record) => (
              <Space>
                <Badge status={record.online ? 'success' : 'error'} />
                <span style={{ fontWeight: 500 }}>{hostname}</span>
              </Space>
            ),
          },
          {
            title: '状态',
            width: 90,
            render: (_, record) => (
              <Tag color={record.online ? 'green' : 'red'}>
                {record.online ? '在线' : '离线'}
              </Tag>
            ),
          },
          {
            title: '外网 IP',
            dataIndex: 'public_ip',
            width: 150,
            render: (ip: string) => ip || '-',
          },
          {
            title: '国家/地区',
            width: 120,
            render: (_, record) => record.country || record.country_code || '-',
          },
          {
            title: 'Agent ID',
            dataIndex: 'agent_id',
            ellipsis: true,
            width: 200,
          },
          {
            title: '显示卡片',
            width: 100,
            align: 'center',
            render: (_, record) => (
              <Switch
                checked={!hiddenSet.has(record.agent_id)}
                loading={prefsSaving}
                onChange={(checked) => toggleAgentHidden(record.agent_id, checked)}
              />
            ),
          },
          {
            title: '操作',
            width: 80,
            align: 'center',
            render: (_, record) => (
              <Popconfirm
                title="删除主机记录"
                description={`确定删除「${record.hostname}」？历史指标将一并清除。`}
                onConfirm={() => handleDelete(record.agent_id)}
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  loading={deletingId === record.agent_id}
                />
              </Popconfirm>
            ),
          },
        ]}
      />
    </PageContainer>
  );
};

export default AdminHosts;
