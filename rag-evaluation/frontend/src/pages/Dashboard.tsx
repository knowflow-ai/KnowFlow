import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Progress, Typography, Space, Tag, Table, Empty, Spin, message, Tooltip } from 'antd';
import {
  InfoCircleOutlined,
} from '@ant-design/icons';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  TrophyOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate } from 'react-router-dom';
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
  completed_tasks: number;
  total_tasks: number;
  running_tasks: number;
  failed_tasks: number;
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  
  // Helper function for health score description
  const getHealthScoreDescription = () => {
    return '综合所有评测报告的质量指标计算得出的系统整体健康度。基于答案正确性、忠实度、上下文精准度、上下文召回率、答案相关性等指标的平均表现，反映知识库的整体服务质量。';
  };

  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    health_score: 0,
    total_evaluations: 0,
    active_datasets: 0,
    avg_processing_time: 0,
    recent_tasks: [],
    metric_scores: [],
    completed_tasks: 0,
    total_tasks: 0,
    running_tasks: 0,
    failed_tasks: 0,
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

      const data = statisticsRes as any;
      console.log('📊 Dashboard statistics data:', data);
      setStats({
        health_score: data.health_score || 0,
        total_evaluations: data.total_evaluations || 0,
        active_datasets: data.active_datasets || 0,
        avg_processing_time: data.avg_processing_time || 0,
        recent_tasks: [],
        metric_scores: data.metric_scores || [],
        completed_tasks: data.completed_tasks || 0,
        total_tasks: data.total_tasks || 0,
        running_tasks: data.running_tasks || 0,
        failed_tasks: data.failed_tasks || 0,
      });
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
      render: (text, record) => (
        <a
          onClick={() => handleTaskClick(record)}
          style={{ cursor: 'pointer' }}
        >
          {text || '未命名任务'}
        </a>
      ),
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

  // 获取指标说明
  const getMetricDescription = (metricName: string) => {
    const descriptions: { [key: string]: string } = {
      '答案正确性': '评估生成的答案是否准确、完整，与参考答案的一致性程度',
      '忠实度': '评估生成的内容是否基于提供的上下文，避免虚构或无关信息',
      '上下文精准度': '评估检索到的上下文片段是否与问题相关，准确度如何',
      '上下文召回率': '评估是否检索到了所有相关上下文，覆盖率如何',
      '答案相关性': '评估生成的答案是否与问题相关，切合度如何',
      '上下文实体召回': '评估上下文中的实体信息是否被正确识别和利用',
      '答案相似度': '评估生成答案与参考答案的语义相似度',
    };
    return descriptions[metricName] || '评估指标的具体含义';
  };

  // 处理任务点击事件
  const handleTaskClick = (record: EvaluationTask) => {
    // 根据任务状态决定跳转逻辑
    if (record.status === 'completed') {
      // 已完成的任务跳转到报告详情页
      navigate(`/reports?task_id=${record.id}`);
    } else {
      // 其他状态的任务跳转到任务详情页
      navigate(`/tasks?task_id=${record.id}`);
    }
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
              title={
                <span>
                  知识库健康度
                  <Tooltip title={getHealthScoreDescription()}>
                    <QuestionCircleOutlined style={{ marginLeft: 4, color: '#1890ff' }} />
                  </Tooltip>
                </span>
              }
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
          <Card title="评测指标得分" extra={<a onClick={() => navigate('/reports')}>查看详情</a>}>
            {stats.metric_scores.length > 0 ? (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                {stats.metric_scores.map((metric) => (
                  <div key={metric.name}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, alignItems: 'center' }}>
                      <Space>
                        <Text>{metric.name}</Text>
                        <Tooltip title={getMetricDescription(metric.name)} placement="topLeft">
                          <InfoCircleOutlined style={{ color: '#1890ff', cursor: 'pointer', fontSize: 14 }} />
                        </Tooltip>
                      </Space>
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
          <Card title="最近评测任务" extra={<a onClick={() => navigate('/tasks')}>查看全部</a>}>
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
        <Col xs={24} lg={12}>
          <Card title="任务状态分布">
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="已完成"
                  value={stats.completed_tasks}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="总任务数"
                  value={stats.total_tasks}
                  prefix={<ExperimentOutlined />}
                  valueStyle={{ color: '#722ed1' }}
                />
              </Col>
            </Row>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="数据集概览">
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="总数据集"
                  value={stats.active_datasets}
                  prefix={<DatabaseOutlined />}
                  suffix="个"
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="平均处理时间"
                  value={stats.avg_processing_time}
                  prefix={<ClockCircleOutlined />}
                  suffix="分钟"
                  precision={1}
                />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;