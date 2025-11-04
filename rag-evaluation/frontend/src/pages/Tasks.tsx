import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Select,
  Input,
  Typography,
  Steps,
  Progress,
  message,
  Tooltip,
  Drawer,
  Timeline,
  Alert,
  Row,
  Col,
  Statistic,
  Badge,
  Divider,
  App,
} from 'antd';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  QuestionCircleOutlined,
  ExperimentOutlined,
  DatabaseOutlined,
  RocketOutlined,
  InfoCircleOutlined,
  ReloadOutlined,
  DeleteOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { chatApi, datasetApi, metricApi, taskApi } from '../services/evaluation';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

interface EvaluationTask {
  id: string;
  name: string;
  kbId: string;
  kbName: string;
  datasetId: string;
  datasetName: string;
  metrics: string[];
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  totalSamples: number;
  processedSamples: number;
  startedAt?: string;
  completedAt?: string;
  estimatedTime?: string;
  createdBy: string;
  createdAt: string;
  score?: number;
  errorMessage?: string;
}

interface ChatAssistant {
  id: string;
  name: string;
  description: string;
  documentCount: number;
  llm?: string;
}

const Tasks: React.FC = () => {
  const appContext = App.useApp();
  console.log('🔍 App.useApp() 返回的内容:', appContext);

  // 检查 modal 是否存在
  if (appContext.modal) {
    console.log('✅ modal 存在于 appContext 中');
  } else {
    console.log('❌ modal 不存在于 appContext 中');
  }

  const [tasks, setTasks] = useState<EvaluationTask[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);

  const [createTaskVisible, setCreateTaskVisible] = useState(false);
  const [selectedTask, setSelectedTask] = useState<EvaluationTask | null>(null);
  const [detailsVisible, setDetailsVisible] = useState(false);
  const [form] = Form.useForm();
  const [chatAssistants, setChatAssistants] = useState<ChatAssistant[]>([]);
  const [datasets, setDatasets] = useState<any[]>([]);
  const [loadingChats, setLoadingChats] = useState(false);
  const [loadingDatasets, setLoadingDatasets] = useState(false);

  // 获取聊天助手列表
  const fetchChatAssistants = async () => {
    setLoadingChats(true);
    try {
      const response = await chatApi.list({ page: 1, page_size: 100 });
      console.log('Chat assistants response:', response);

      // RAGFlow API 返回格式: {code: 0, data: [...]}
      if (response.code === 0 && response.data) {
        const chats = response.data;
        console.log('Parsed chat assistants:', chats);

        setChatAssistants(chats.map((chat: any) => ({
          id: chat.id,
          name: chat.name,
          description: chat.description || 'RAGFlow 对话助手',
          documentCount: chat.datasets?.length || 0,
          llm: chat.llm
        })));

        message.success(`成功获取 ${chats.length} 个对话助手`);
      } else {
        console.error('RAGFlow API error:', response);
        message.error(`获取对话助手失败: ${response.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to fetch chat assistants:', error);
      message.error('获取对话助手列表失败');
    } finally {
      setLoadingChats(false);
    }
  };

  // 获取数据集列表
  const fetchDatasets = async () => {
    setLoadingDatasets(true);
    try {
      const response = await datasetApi.list({ limit: 100 });
      if (response.datasets) {
        setDatasets(response.datasets.map((ds: any) => ({
          id: ds.id,
          name: ds.name,
          samples: ds.num_samples
        })));
      }
    } catch (error) {
      console.error('Failed to fetch datasets:', error);
      message.error('获取数据集列表失败');
      setDatasets([]);
    } finally {
      setLoadingDatasets(false);
    }
  };

  // 可用的评测指标
  const [availableMetrics, setAvailableMetrics] = useState<
    Array<{ value: string; label: string; description: string }>
  >([]);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  // 获取任务列表
  const fetchTasks = async () => {
    console.log('🔄 开始获取任务列表');
    setLoadingTasks(true);
    try {
      const response = await taskApi.list({ limit: 100 });
      console.log('🔄 任务列表API响应:', response);

      if (response.tasks) {
        // 转换 API 数据格式为组件使用的格式
        const formattedTasks = response.tasks.map((task) => ({
          id: task.id,
          name: task.name || `评测任务 #${task.id}`,
          kbId: task.chat_id, // 后端返回 chat_id，前端使用 kbId
          kbName: task.chat_id, // TODO: 从对话助手列表中获取名称
          datasetId: task.dataset_id,
          datasetName: task.dataset_id, // TODO: 从数据集列表中获取名称
          metrics: task.metrics,
          status: task.status,
          progress: task.progress,
          totalSamples: task.total_samples,
          processedSamples: task.processed_samples,
          startedAt: task.started_at,
          completedAt: task.completed_at,
          createdBy: 'admin', // TODO: 从 task 数据中获取
          createdAt: task.created_at,
          errorMessage: task.error_message,
        }));
        console.log('🔄 格式化后的任务列表:', formattedTasks);
        console.log('🔄 当前任务数量:', formattedTasks.length);
        setTasks(formattedTasks);
        console.log('🔄 setTasks已调用，状态已更新');
      } else {
        console.log('🔄 响应中没有tasks字段');
        setTasks([]);
      }
    } catch (error) {
      console.error('❌ 获取任务列表失败:', error);
      message.error('获取任务列表失败');
      setTasks([]);
    } finally {
      setLoadingTasks(false);
      console.log('🔄 fetchTasks完成，loading设置为false');
    }
  };

  // 组件加载时获取数据
  useEffect(() => {
    fetchTasks();
    fetchChatAssistants();
    fetchDatasets();
    fetchMetrics();
  }, []);

  // 自动刷新任务列表 - 每2秒更新一次
  useEffect(() => {
    const intervalId = setInterval(() => {
      // 检查是否有运行中或等待中的任务
      const hasActiveTasks = tasks.some(task =>
        task.status === 'running' || task.status === 'pending'
      );

      if (hasActiveTasks) {
        console.log('🔄 自动刷新任务列表 (检测到活跃任务)');
        fetchTasks();
      }
    }, 2000); // 2秒刷新一次

    // 清理函数：组件卸载时清除定时器
    return () => {
      console.log('🔄 清除任务列表自动刷新定时器');
      clearInterval(intervalId);
    };
  }, [tasks]); // 依赖 tasks，当任务列表变化时重新设置定时器

  const fetchMetrics = async () => {
    setLoadingMetrics(true);
    try {
      const response = await metricApi.list();
      const metrics = (response.metrics || []).map((m) => ({
        value: m.name,
        label: m.display_name,
        description: m.description,
      }));
      setAvailableMetrics(metrics);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
      message.error('获取评测指标失败');
    } finally {
      setLoadingMetrics(false);
    }
  };

  const getStatusConfig = (status: EvaluationTask['status']) => {
    const configs = {
      pending: { color: 'default', icon: <ClockCircleOutlined />, text: '等待中' },
      running: { color: 'processing', icon: <SyncOutlined spin />, text: '运行中' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
      cancelled: { color: 'warning', icon: <CloseCircleOutlined />, text: '已取消' },
    };
    return configs[status] || { color: 'default', icon: <QuestionCircleOutlined />, text: '未知状态' };
  };

  const columns: ColumnsType<EvaluationTask> = [
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <a onClick={() => showTaskDetails(record)}>{text}</a>
      ),
    },
    {
      title: '对话助手',
      dataIndex: 'kbName',
      key: 'kbName',
      render: (text) => (
        <Space>
          <DatabaseOutlined />
          {text}
        </Space>
      ),
    },
    {
      title: '数据集',
      dataIndex: 'datasetName',
      key: 'datasetName',
    },
    {
      title: '评测指标',
      dataIndex: 'metrics',
      key: 'metrics',
      render: (metrics: string[]) => (
        <Space wrap>
          {metrics.map((metric) => (
            <Tag key={metric}>
              {availableMetrics.find((m) => m.value === metric)?.label || metric}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        const config = getStatusConfig(status);
        return (
          <Tag icon={config.icon} color={config.color}>
            {config.text}
          </Tag>
        );
      },
      filters: [
        { text: '等待中', value: 'pending' },
        { text: '运行中', value: 'running' },
        { text: '已完成', value: 'completed' },
        { text: '失败', value: 'failed' },
      ],
      onFilter: (value, record) => record.status === value,
    },
    {
      title: '进度',
      key: 'progress',
      render: (_, record) => (
        <div style={{ minWidth: 120 }}>
          <Progress
            percent={record.progress}
            size="small"
            status={record.status === 'failed' ? 'exception' : undefined}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {record.processedSamples}/{record.totalSamples}
          </Text>
        </div>
      ),
    },
    {
      title: '评分',
      dataIndex: 'score',
      key: 'score',
      render: (score) => {
        if (!score) return '-';
        const color = score >= 80 ? 'green' : score >= 60 ? 'orange' : 'red';
        return <Badge count={score} style={{ backgroundColor: color }} />;
      },
      sorter: (a, b) => (a.score || 0) - (b.score || 0),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      sorter: (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="small">
          {record.status === 'pending' && (
            <Tooltip title="开始">
              <Button
                size="small"
                type="link"
                icon={<PlayCircleOutlined />}
                onClick={() => startTask(record.id)}
              />
            </Tooltip>
          )}
          {record.status === 'running' && (
            <Tooltip title="暂停">
              <Button
                size="small"
                type="link"
                icon={<PauseCircleOutlined />}
                onClick={() => pauseTask(record.id)}
              />
            </Tooltip>
          )}
          {record.status === 'completed' && (
            <Tooltip title="查看报告">
              <Button
                size="small"
                type="link"
                icon={<EyeOutlined />}
                onClick={() => viewReport(record.id)}
              />
            </Tooltip>
          )}
          {record.status === 'failed' && (
            <Tooltip title="重试">
              <Button
                size="small"
                type="link"
                icon={<ReloadOutlined />}
                onClick={() => retryTask(record.id)}
              />
            </Tooltip>
          )}
          <Tooltip title="删除">
            <Button
              size="small"
              type="link"
              danger
              icon={<DeleteOutlined />}
              onClick={() => {
                console.log('🗑️ 删除按钮被点击，任务ID:', record.id);
                deleteTask(record.id);
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const showTaskDetails = (task: EvaluationTask) => {
    setSelectedTask(task);
    setDetailsVisible(true);
  };

  const startTask = async (taskId: string) => {
    try {
      await taskApi.start(taskId);
      message.success('任务已开始执行');
      fetchTasks(); // 刷新任务列表
    } catch (error) {
      console.error('Failed to start task:', error);
      message.error('开始任务失败');
    }
  };

  const pauseTask = async (taskId: string) => {
    try {
      await taskApi.pause(taskId);
      message.success('任务已暂停');
      fetchTasks(); // 刷新任务列表
    } catch (error) {
      console.error('Failed to pause task:', error);
      message.error('暂停任务失败');
    }
  };

  const viewReport = (taskId: string) => {
    // 跳转到报告页面
    window.location.href = `/reports?taskId=${taskId}`;
  };

  const retryTask = async (taskId: string) => {
    try {
      await taskApi.retry(taskId);
      message.success('任务已重新开始');
      fetchTasks(); // 刷新任务列表
    } catch (error) {
      console.error('Failed to retry task:', error);
      message.error('重试任务失败');
    }
  };

  const deleteTask = (taskId: string) => {
    console.log('🗑️ deleteTask函数被调用，任务ID:', taskId);

    // 找到要删除的任务名称用于显示
    const taskToDelete = tasks.find(task => task.id === taskId);
    const taskName = taskToDelete?.name || taskId;

    console.log('🗑️ 准备显示确认对话框，任务名称:', taskName);
    console.log('🗑️ appContext.modal:', appContext.modal);

    // 检查 modal 是否存在并使用
    if (appContext.modal && typeof appContext.modal.confirm === 'function') {
      console.log('🗑️ 使用 appContext.modal.confirm');
      appContext.modal.confirm({
        title: '确认删除',
        content: (
          <div>
            <p>确定要删除任务 <strong>"{taskName}"</strong> 吗？</p>
            <p style={{ color: '#ff4d4f', fontSize: '12px' }}>此操作无法撤销。</p>
          </div>
        ),
        okText: '删除',
        okType: 'danger',
        cancelText: '取消',
        width: 400,
        onOk: async () => {
          console.log('🗑️ 用户确认删除，开始调用API...');
          executeDelete(taskId);
        },
        onCancel: () => {
          console.log('🗑️ 用户取消了删除操作');
        },
      });
    } else {
      console.log('🗑️ modal 不存在，回退到静态 Modal.confirm');
      // 回退到静态方法
      Modal.confirm({
        title: '确认删除',
        content: (
          <div>
            <p>确定要删除任务 <strong>"{taskName}"</strong> 吗？</p>
            <p style={{ color: '#ff4d4f', fontSize: '12px' }}>此操作无法撤销。</p>
          </div>
        ),
        okText: '删除',
        okType: 'danger',
        cancelText: '取消',
        width: 400,
        onOk: async () => {
          console.log('🗑️ 用户确认删除，开始调用API...');
          executeDelete(taskId);
        },
        onCancel: () => {
          console.log('🗑️ 用户取消了删除操作');
        },
      });
    }
  };

  const executeDelete = async (taskId: string) => {
    try {
      console.log('🗑️ 调用taskApi.delete，任务ID:', taskId);
      const result = await taskApi.delete(taskId);
      console.log('🗑️ 删除API调用成功，结果:', result);

      // 使用静态方法 message（为了兼容性）
      message.success('任务已删除');
      console.log('🗑️ 成功消息已显示，开始刷新任务列表');

      // 添加短暂延迟确保删除操作完成后再刷新列表
      setTimeout(() => {
        console.log('🗑️ 执行fetchTasks刷新列表');
        fetchTasks();
      }, 500);
    } catch (error) {
      console.error('❌ Failed to delete task:', error);
      message.error(`删除任务失败: ${error instanceof Error ? error.message : '未知错误'}`);
    }
  };

  const handleCreateTask = async () => {
    try {
      const values = await form.validateFields();

      // 调用 API 创建任务
      const response = await taskApi.create({
        name: values.name,
        chat_id: values.chatId,
        dataset_id: values.datasetId,
        metrics: values.metrics,
        llm_model: 'gpt-4', // TODO: 从配置中获取
        batch_size: 10,
      });

      message.success('评测任务创建成功');
      setCreateTaskVisible(false);
      form.resetFields();

      // 刷新任务列表
      fetchTasks();
    } catch (error) {
      console.error('Failed to create task:', error);
      message.error('创建评测任务失败');
    }
  };

  // 统计数据
  const stats = {
    total: tasks.length,
    pending: tasks.filter((t) => t.status === 'pending').length,
    running: tasks.filter((t) => t.status === 'running').length,
    completed: tasks.filter((t) => t.status === 'completed').length,
    failed: tasks.filter((t) => t.status === 'failed').length,
  };

  return (
    <div>
      <Title level={2}>评测任务</Title>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginTop: 24, marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="全部任务" value={stats.total} prefix={<ExperimentOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="运行中"
              value={stats.running}
              prefix={<SyncOutlined spin />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已完成"
              value={stats.completed}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="失败"
              value={stats.failed}
              prefix={<CloseCircleOutlined />}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 任务列表 */}
      <Card>
        <div style={{ marginBottom: 16 }}>
          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={() => setCreateTaskVisible(true)}
          >
            创建评测任务
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loadingTasks}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 个任务`,
          }}
        />
      </Card>

      {/* 创建任务模态框 */}
      <Modal
        title="创建评测任务"
        open={createTaskVisible}
        onOk={handleCreateTask}
        onCancel={() => setCreateTaskVisible(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="任务名称"
            name="name"
            rules={[{ required: false }]}
          >
            <Input placeholder="可选，如：金融知识库周评测" />
          </Form.Item>

          <Form.Item
            label={
              <Space>
                选择对话助手
                <Tooltip title="刷新对话助手列表">
                  <Button
                    type="link"
                    size="small"
                    icon={<ReloadOutlined />}
                    loading={loadingChats}
                    onClick={fetchChatAssistants}
                  />
                </Tooltip>
              </Space>
            }
            name="chatId"
            rules={[{ required: true, message: '请选择对话助手' }]}
          >
            <Select
              placeholder="请选择要评测的对话助手"
              loading={loadingChats}
              notFoundContent={loadingChats ? '加载中...' : '暂无对话助手'}
            >
              {chatAssistants.map((chat) => (
                <Option key={chat.id} value={chat.id}>
                  <Space>
                    <DatabaseOutlined />
                    {chat.name}
                    <Text type="secondary">({chat.documentCount} 文档)</Text>
                  </Space>
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label={
              <Space>
                选择数据集
                <Tooltip title="刷新数据集列表">
                  <Button
                    type="link"
                    size="small"
                    icon={<ReloadOutlined />}
                    loading={loadingDatasets}
                    onClick={fetchDatasets}
                  />
                </Tooltip>
              </Space>
            }
            name="datasetId"
            rules={[{ required: true, message: '请选择数据集' }]}
          >
            <Select
              placeholder="请选择评测数据集"
              loading={loadingDatasets}
              notFoundContent={loadingDatasets ? '加载中...' : '暂无数据集'}
            >
              {datasets.map((ds) => (
                <Option key={ds.id} value={ds.id}>
                  {ds.name} ({ds.samples} 样本)
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="评测指标"
            name="metrics"
            rules={[{ required: true, message: '请至少选择一个评测指标' }]}
          >
            <Select
              mode="multiple"
              placeholder="请选择评测指标"
              optionLabelProp="label"
            >
              {availableMetrics.map((metric) => (
                <Option
                  key={metric.value}
                  value={metric.value}
                  label={metric.label}
                >
                  <div>
                    <div>{metric.label}</div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {metric.description}
                    </Text>
                  </div>
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Alert
            message="提示"
            description="评测任务创建后将自动加入队列，系统会按顺序执行。"
            type="info"
            showIcon
          />
        </Form>
      </Modal>

      {/* 任务详情抽屉 */}
      <Drawer
        title="任务详情"
        width={600}
        open={detailsVisible}
        onClose={() => setDetailsVisible(false)}
      >
        {selectedTask && (
          <div>
            <Paragraph>
              <Title level={4}>{selectedTask.name}</Title>
            </Paragraph>

            <Divider />

            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Text type="secondary">对话助手：</Text>
                <br />
                <Text strong>{selectedTask.kbName}</Text>
              </Col>
              <Col span={12}>
                <Text type="secondary">数据集：</Text>
                <br />
                <Text strong>{selectedTask.datasetName}</Text>
              </Col>
              <Col span={12}>
                <Text type="secondary">状态：</Text>
                <br />
                <Tag
                  icon={getStatusConfig(selectedTask.status).icon}
                  color={getStatusConfig(selectedTask.status).color}
                >
                  {getStatusConfig(selectedTask.status).text}
                </Tag>
              </Col>
              <Col span={12}>
                <Text type="secondary">进度：</Text>
                <br />
                <Progress percent={selectedTask.progress} />
              </Col>
              <Col span={12}>
                <Text type="secondary">样本进度：</Text>
                <br />
                <Text>
                  {selectedTask.processedSamples} / {selectedTask.totalSamples}
                </Text>
              </Col>
              <Col span={12}>
                <Text type="secondary">评分：</Text>
                <br />
                <Text strong>{selectedTask.score || '-'}</Text>
              </Col>
            </Row>

            <Divider />

            <Title level={5}>评测指标</Title>
            <Space wrap>
              {selectedTask.metrics.map((metric) => (
                <Tag key={metric} color="blue">
                  {availableMetrics.find((m) => m.value === metric)?.label || metric}
                </Tag>
              ))}
            </Space>

            <Divider />

            <Title level={5}>执行时间线</Title>
            <Timeline>
              <Timeline.Item color="green">
                创建于 {selectedTask.createdAt}
              </Timeline.Item>
              {selectedTask.startedAt && (
                <Timeline.Item color="blue">
                  开始于 {selectedTask.startedAt}
                </Timeline.Item>
              )}
              {selectedTask.completedAt && (
                <Timeline.Item color="green">
                  完成于 {selectedTask.completedAt}
                </Timeline.Item>
              )}
              {selectedTask.errorMessage && (
                <Timeline.Item color="red">
                  错误：{selectedTask.errorMessage}
                </Timeline.Item>
              )}
            </Timeline>
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default Tasks;