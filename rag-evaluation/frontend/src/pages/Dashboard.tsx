import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Progress, Typography, Space, Tag, Table, Empty, Spin, message } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  TrophyOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { systemApi, taskApi } from '../services/evaluation';
import type { EvaluationTask } from '../services/evaluation';

const { Title, Text } = Typography;

interface MetricScore {
  name: string;
  score: number;
  trend: 'up' | 'down' | 'stable';
}

interface DashboardStats {
  health_score: number;
  total_evaluations: number;
  active_datasets: number;
  avg_processing_time: number;
  recent_tasks: any[];
  metric_scores: MetricScore[];
}

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    health_score: 0,
    total_evaluations: 0,
    active_datasets: 0,
    avg_processing_time: 0,
    recent_tasks: [],
    metric_scores: [],
  });

  const [recentTasks, setRecentTasks] = useState<EvaluationTask[]>([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [statisticsRes, tasksRes] = await Promise.all([
        systemApi.getStatistics(),
        taskApi.list({ limit: 5 }),
      ]);

      setStats(statisticsRes as DashboardStats);
      setRecentTasks(tasksRes.tasks || []);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      message.error('获取仪表盘数据失败');
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<EvaluationTask> = [
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      render: (text) => <a>{text || '-'}</a>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        const config = {
          completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
          running: { color: 'processing', icon: <SyncOutlined spin />, text: '运行中' },
          failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
          pending: { color: 'default', icon: <ClockCircleOutlined />, text: '等待中' },
          cancelled: { color: 'default', icon: <CloseCircleOutlined />, text: '已取消' },
        };
        const { color, icon, text } = config[status] || config.pending;
        return (
          <Tag icon={icon} color={color}>
            {text}
          </Tag>
        );
      },
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      render: (progress, record) => {
        if (record.status === 'pending') return '-';
        return (
          <Progress
            percent={progress}
            size="small"
            status={record.status === 'failed' ? 'exception' : record.status === 'completed' ? 'success' : 'active'}
          />
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text) => text ? new Date(text).toLocaleString('zh-CN') : '-',
    },
  ];

  const getHealthColor = (score: number) => {
    if (score >= 80) return '#52c41a';
    if (score >= 60) return '#faad14';
    return '#ff4d4f';
  };

  if (loading && recentTasks.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  return (
    <div>
      <Title level={2}>评测仪表盘</Title>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="知识库健康度"
              value={stats.health_score}
              suffix="/100"
              prefix={<TrophyOutlined style={{ color: getHealthColor(stats.health_score) }} />}
              valueStyle={{ color: getHealthColor(stats.health_score) }}
            />
            <Progress
              percent={stats.health_score}
              strokeColor={getHealthColor(stats.health_score)}
              showInfo={false}
              style={{ marginTop: 8 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="总评测次数"
              value={stats.total_evaluations}
              prefix={<ExperimentOutlined />}
              suffix="次"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="活跃数据集"
              value={stats.active_datasets}
              prefix={<DatabaseOutlined />}
              suffix="个"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="平均处理时间"
              value={stats.avg_processing_time}
              prefix={<ClockCircleOutlined />}
              suffix="分钟"
              precision={1}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="评测指标得分" extra={<a>查看详情</a>}>
            {stats.metric_scores.length > 0 ? (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                {stats.metric_scores.map((metric) => (
                  <div key={metric.name}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <Text>{metric.name}</Text>
                      <Space>
                        <Text strong>{metric.score}%</Text>
                        {metric.trend === 'up' && <Tag color="success">↑</Tag>}
                        {metric.trend === 'down' && <Tag color="error">↓</Tag>}
                        {metric.trend === 'stable' && <Tag>→</Tag>}
                      </Space>
                    </div>
                    <Progress
                      percent={metric.score}
                      showInfo={false}
                      strokeColor={metric.score >= 80 ? '#52c41a' : metric.score >= 60 ? '#1890ff' : '#ff4d4f'}
                    />
                  </div>
                ))}
              </Space>
            ) : (
              <Empty description="暂无评测指标数据" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="最近评测任务" extra={<a>查看全部</a>}>
            <Table
              columns={columns}
              dataSource={recentTasks}
              pagination={false}
              size="small"
              rowKey="id"
              locale={{ emptyText: '暂无评测任务' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col span={24}>
          <Card title="评测趋势">
            <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Empty description="图表组件待集成" />
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;