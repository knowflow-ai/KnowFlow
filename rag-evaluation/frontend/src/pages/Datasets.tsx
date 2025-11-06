import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Upload,
  message,
  Typography,
  Dropdown,
  Input,
  Form,
  Select,
  Tabs,
  Descriptions,
  List,
  Empty,
  Statistic,
  Spin,
} from 'antd';
import {
  UploadOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  DownloadOutlined,
  DeleteOutlined,
  EyeOutlined,
  PlusOutlined,
  SearchOutlined,
  FileExcelOutlined,
  FileMarkdownOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { datasetApi, taskApi, chatApi, metricApi } from '../services/evaluation';
import type { Dataset as ApiDataset, Metric, TaskCreateParams } from '../services/evaluation';
import { useBatchDelete } from '../hooks/useBatchDelete';
import { BatchActionBar } from '../components/BatchActionBar';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;
const { Dragger } = Upload;

interface DatasetSample {
  question: string;
  expected_answer?: string;
  contexts?: string[];
}

const Datasets: React.FC = () => {
  const [datasets, setDatasets] = useState<ApiDataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadVisible, setUploadVisible] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [generateVisible, setGenerateVisible] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [createTaskVisible, setCreateTaskVisible] = useState(false);
  const [creatingTask, setCreatingTask] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<ApiDataset | null>(null);
  const [datasetSamples, setDatasetSamples] = useState<DatasetSample[]>([]);
  const [samplesLoading, setSamplesLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [chatAssistants, setChatAssistants] = useState<any[]>([]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loadingChats, setLoadingChats] = useState(false);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [form] = Form.useForm();
  const [generateForm] = Form.useForm();
  const [createTaskForm] = Form.useForm();

  useEffect(() => {
    fetchDatasets();
  }, []);

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const response = await datasetApi.list({ limit: 100 });
      setDatasets(response.datasets || []);
    } catch (error) {
      console.error('Failed to fetch datasets:', error);
      message.error('获取数据集列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 使用统一的批量删除 Hook
  const {
    rowSelection,
    batchDeleting,
    handleBatchDelete,
    clearSelection,
    selectedRowKeys,
  } = useBatchDelete({
    apiCall: datasetApi.batchDelete,
    itemName: '数据集',
    onSuccess: fetchDatasets,
    permanentWarning: true,
  });

  const columns: ColumnsType<ApiDataset> = [
    {
      title: '数据集名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          {record.file_type === 'csv' && <FileExcelOutlined />}
          {record.file_type === 'json' && <FileTextOutlined />}
          {record.file_type === 'md' && <FileMarkdownOutlined />}
          <a onClick={() => handlePreview(record)}>{text}</a>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '样本数',
      dataIndex: 'num_samples',
      key: 'num_samples',
      sorter: (a, b) => a.num_samples - b.num_samples,
    },
    {
      title: '数据完整性',
      key: 'completeness',
      render: (_, record) => (
        <Space>
          {record.has_reference && <Tag color="green">包含参考答案</Tag>}
          {record.has_contexts && <Tag color="blue">包含上下文</Tag>}
          {!record.has_reference && !record.has_contexts && <Tag>仅问题</Tag>}
        </Space>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text) => text ? new Date(text).toLocaleString('zh-CN') : '-',
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <Button size="small" icon={<EyeOutlined />} onClick={() => handlePreview(record)}>
            预览
          </Button>
          <Button size="small" type="primary" onClick={() => handleCreateTask(record)}>
            创建评测
          </Button>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'delete',
                  label: '删除',
                  icon: <DeleteOutlined />,
                  danger: true,
                  onClick: () => handleDelete(record),
                },
              ],
            }}
          >
            <Button size="small">更多</Button>
          </Dropdown>
        </Space>
      ),
    },
  ];

  const handlePreview = async (dataset: ApiDataset) => {
    setSelectedDataset(dataset);
    setPreviewVisible(true);
    setSamplesLoading(true);
    try {
      const response = await datasetApi.getSamples(dataset.id, { limit: 10 });
      setDatasetSamples(response.samples || []);
    } catch (error) {
      console.error('Failed to fetch dataset samples:', error);
      message.error('获取数据集样本失败');
    } finally {
      setSamplesLoading(false);
    }
  };

  const handleCreateTask = async (dataset: ApiDataset) => {
    setSelectedDataset(dataset);
    setCreateTaskVisible(true);

    // 加载 Chat 助手列表
    if (chatAssistants.length === 0) {
      await fetchChatAssistants();
    }

    // 加载指标列表
    if (metrics.length === 0) {
      await fetchMetrics();
    }

    // 设置表单默认值
    createTaskForm.setFieldsValue({
      dataset_id: dataset.id,
      name: `评测任务 - ${dataset.name}`,
    });
  };

  const fetchChatAssistants = async () => {
    setLoadingChats(true);
    try {
      const response = await chatApi.list({ page_size: 100 });
      // RAGFlow API 返回格式: {code: 0, data: [...]}
      if (response.code === 0 && response.data) {
        setChatAssistants(Array.isArray(response.data) ? response.data : []);
      }
    } catch (error) {
      console.error('Failed to fetch chat assistants:', error);
      message.error('获取对话助手列表失败');
    } finally {
      setLoadingChats(false);
    }
  };

  const fetchMetrics = async () => {
    setLoadingMetrics(true);
    try {
      const response = await metricApi.list();
      setMetrics(response.metrics || []);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
      message.error('获取评测指标失败');
    } finally {
      setLoadingMetrics(false);
    }
  };

  const handleCreateTaskSubmit = async () => {
    try {
      const values = await createTaskForm.validateFields();
      setCreatingTask(true);

      const taskParams: TaskCreateParams = {
        name: values.name,
        chat_id: values.chat_id,
        dataset_id: selectedDataset!.id,
        metrics: values.metrics,
        batch_size: values.batch_size || 10,
      };

      const task = await taskApi.create(taskParams);
      message.success(`评测任务创建成功: ${task.name || task.id}`);

      setCreateTaskVisible(false);
      createTaskForm.resetFields();
      setSelectedDataset(null);

      // 可以跳转到任务页面
      // navigate('/tasks');
    } catch (error) {
      console.error('Failed to create task:', error);
      message.error('创建评测任务失败');
    } finally {
      setCreatingTask(false);
    }
  };

  const handleDelete = async (dataset: ApiDataset) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除数据集"${dataset.name}"吗？此操作不可恢复。`,
      onOk: async () => {
        try {
          await datasetApi.delete(dataset.id);
          message.success('删除成功');
          fetchDatasets();
        } catch (error) {
          console.error('Failed to delete dataset:', error);
          message.error('删除失败');
        }
      },
    });
  };

  
  const handleUpload = async (file: File) => {
    const formValues = form.getFieldsValue();

    try {
      await datasetApi.upload(file, {
        name: formValues.name || file.name,
        description: formValues.description || '',
      });
      message.success(`${file.name} 上传成功`);
      setUploadVisible(false);
      form.resetFields();
      fetchDatasets();
    } catch (error) {
      console.error('Failed to upload dataset:', error);
      message.error(`${file.name} 上传失败`);
    }

    return false;
  };

  const handleGenerate = async () => {
    try {
      const values = await generateForm.validateFields();
      setGenerating(true);

      const response = await datasetApi.generateSample(values.type);
      message.success(`示例数据集生成成功: ${response.name}`);
      setGenerateVisible(false);
      generateForm.resetFields();
      fetchDatasets();
    } catch (error) {
      console.error('Failed to generate sample dataset:', error);
      message.error('生成示例数据集失败');
    } finally {
      setGenerating(false);
    }
  };

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    accept: '.csv,.json,.jsonl,.xlsx,.txt',
    beforeUpload: handleUpload,
    showUploadList: false,
  };

  return (
    <div>
      <Title level={2}>数据集管理</Title>

      <Card style={{ marginTop: 24 }}>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
          <Space>
            <Search
              placeholder="搜索数据集"
              allowClear
              onSearch={setSearchText}
              style={{ width: 300 }}
            />
            <Select defaultValue="all" style={{ width: 120 }}>
              <Select.Option value="all">全部类型</Select.Option>
              <Select.Option value="csv">CSV</Select.Option>
              <Select.Option value="json">JSON</Select.Option>
              <Select.Option value="excel">Excel</Select.Option>
            </Select>
          </Space>
          <Space>
            <Button
              type="primary"
              icon={<UploadOutlined />}
              onClick={() => setUploadVisible(true)}
            >
              上传数据集
            </Button>
            <Button icon={<PlusOutlined />} onClick={() => setGenerateVisible(true)}>
              生成示例数据集
            </Button>
          </Space>
        </div>

        <BatchActionBar
          selectedCount={selectedRowKeys.length}
          onDelete={handleBatchDelete}
          onCancel={clearSelection}
          deleting={batchDeleting}
          itemName="数据集"
        />

        <Table
          columns={columns}
          dataSource={datasets}
          loading={loading}
          rowKey="id"
          rowSelection={rowSelection}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 个数据集`,
          }}
          locale={{ emptyText: '暂无数据集' }}
        />
      </Card>

      {/* 上传数据集模态框 */}
      <Modal
        title="上传评测数据集"
        open={uploadVisible}
        onCancel={() => {
          setUploadVisible(false);
          form.resetFields();
        }}
        footer={null}
        width={600}
      >
        <Form layout="vertical" form={form}>
          <Form.Item
            label="数据集名称"
            name="name"
            rules={[{ required: true, message: '请输入数据集名称' }]}
          >
            <Input placeholder="例如：金融问答数据集" />
          </Form.Item>

          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} placeholder="简要描述数据集的内容和用途" />
          </Form.Item>

          <Form.Item label="上传文件">
            <Dragger {...uploadProps}>
              <p className="ant-upload-drag-icon">
                <DatabaseOutlined style={{ fontSize: 48, color: '#1890ff' }} />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">
                支持 CSV, JSON, JSONL, Excel, TXT 格式
                <br />
                文件大小不超过 10MB
              </p>
            </Dragger>
          </Form.Item>

          <div style={{ marginTop: 16 }}>
            <Title level={5}>数据格式要求</Title>
            <Paragraph>
              <ul>
                <li>
                  <strong>必需字段：</strong>question（问题）
                </li>
                <li>
                  <strong>可选字段：</strong>expected_answer（参考答案）, contexts（上下文）
                </li>
                <li>CSV 格式：第一行为表头，每行一个样本</li>
                <li>JSON 格式：数组形式，每个元素为一个样本对象</li>
              </ul>
            </Paragraph>
          </div>
        </Form>
      </Modal>

      {/* 生成示例数据集模态框 */}
      <Modal
        title="生成示例数据集"
        open={generateVisible}
        onOk={handleGenerate}
        onCancel={() => {
          setGenerateVisible(false);
          generateForm.resetFields();
        }}
        confirmLoading={generating}
        okText="生成"
        cancelText="取消"
        width={600}
      >
        <Form layout="vertical" form={generateForm}>
          <Form.Item
            label="数据集类型"
            name="type"
            rules={[{ required: true, message: '请选择数据集类型' }]}
            initialValue="basic"
          >
            <Select>
              <Select.Option value="basic">
                <div>
                  <div><strong>基础数据集</strong></div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    仅包含问题，适合测试基本的 RAG 流程
                  </Text>
                </div>
              </Select.Option>
              <Select.Option value="with_reference">
                <div>
                  <div><strong>带参考答案的数据集</strong></div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    包含问题和参考答案，适合测试答案正确性
                  </Text>
                </div>
              </Select.Option>
              <Select.Option value="with_contexts">
                <div>
                  <div><strong>带上下文的数据集</strong></div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    包含问题、答案和上下文，适合全面评测
                  </Text>
                </div>
              </Select.Option>
            </Select>
          </Form.Item>

          <div style={{ marginTop: 16 }}>
            <Title level={5}>说明</Title>
            <Paragraph>
              <ul>
                <li>示例数据集将自动生成 5 个样本</li>
                <li>内容为关于 RAGFlow 的常见问题</li>
                <li>可用于快速测试评测系统功能</li>
                <li>生成后可在数据集列表中查看和使用</li>
              </ul>
            </Paragraph>
          </div>
        </Form>
      </Modal>

      {/* 预览数据集模态框 */}
      <Modal
        title={`预览数据集：${selectedDataset?.name}`}
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        width={900}
        footer={[
          <Button key="close" onClick={() => setPreviewVisible(false)}>
            关闭
          </Button>,
        ]}
      >
        {selectedDataset && (
          <Tabs defaultActiveKey="info">
            <Tabs.TabPane tab="基本信息" key="info">
              <Descriptions column={2}>
                <Descriptions.Item label="数据集ID">{selectedDataset.id}</Descriptions.Item>
                <Descriptions.Item label="文件类型">{selectedDataset.file_type.toUpperCase()}</Descriptions.Item>
                <Descriptions.Item label="样本数量">{selectedDataset.num_samples}</Descriptions.Item>
                <Descriptions.Item label="包含参考答案">
                  {selectedDataset.has_reference ? '是' : '否'}
                </Descriptions.Item>
                <Descriptions.Item label="包含上下文">
                  {selectedDataset.has_contexts ? '是' : '否'}
                </Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {new Date(selectedDataset.created_at).toLocaleString('zh-CN')}
                </Descriptions.Item>
                <Descriptions.Item label="创建者">{selectedDataset.created_by}</Descriptions.Item>
                <Descriptions.Item label="描述" span={2}>
                  {selectedDataset.description || '-'}
                </Descriptions.Item>
              </Descriptions>
            </Tabs.TabPane>
            <Tabs.TabPane tab="数据样例" key="samples">
              {samplesLoading ? (
                <div style={{ textAlign: 'center', padding: '40px' }}>
                  <Spin tip="加载样本数据中..." />
                </div>
              ) : (
                <List
                  dataSource={datasetSamples}
                  locale={{ emptyText: '暂无样本数据' }}
                  renderItem={(item, index) => (
                    <List.Item>
                      <List.Item.Meta
                        title={<Text strong>样本 {index + 1}：</Text>}
                        description={
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <div>
                              <Text type="secondary">问题：</Text>
                              <Text>{item.question}</Text>
                            </div>
                            {item.expected_answer && (
                              <div>
                                <Text type="secondary">参考答案：</Text>
                                <Text>{item.expected_answer}</Text>
                              </div>
                            )}
                            {item.contexts && item.contexts.length > 0 && (
                              <div>
                                <Text type="secondary">上下文：</Text>
                                <Text>{item.contexts.join(', ')}</Text>
                              </div>
                            )}
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </Tabs.TabPane>
          </Tabs>
        )}
      </Modal>

      {/* 创建评测任务模态框 */}
      <Modal
        title={`创建评测任务：${selectedDataset?.name || ''}`}
        open={createTaskVisible}
        onOk={handleCreateTaskSubmit}
        onCancel={() => {
          setCreateTaskVisible(false);
          createTaskForm.resetFields();
          setSelectedDataset(null);
        }}
        confirmLoading={creatingTask}
        okText="创建任务"
        cancelText="取消"
        width={700}
      >
        <Form layout="vertical" form={createTaskForm}>
          <Form.Item
            label="任务名称"
            name="name"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input placeholder="例如：金融知识库-基础评测" />
          </Form.Item>

          <Form.Item
            label="选择对话助手"
            name="chat_id"
            rules={[{ required: true, message: '请选择要评测的对话助手' }]}
          >
            <Select
              placeholder="选择要评测的对话助手 (Chat Assistant)"
              loading={loadingChats}
              showSearch
              optionFilterProp="children"
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={chatAssistants.map((chat) => ({
                label: `${chat.name} (${chat.dataset_ids?.length || 0} 个知识库)`,
                value: chat.id,
              }))}
            />
          </Form.Item>

          <Form.Item
            label="选择评测指标"
            name="metrics"
            rules={[{ required: true, message: '请至少选择一个评测指标' }]}
          >
            <Select
              mode="multiple"
              placeholder="选择要使用的评测指标"
              loading={loadingMetrics}
              options={metrics.map((metric) => ({
                label: `${metric.display_name} - ${metric.description}`,
                value: metric.name,
              }))}
            />
          </Form.Item>

          <Form.Item
            label="批处理大小"
            name="batch_size"
            initialValue={10}
            tooltip="每批处理的样本数量，影响处理速度和内存占用"
          >
            <Select>
              <Select.Option value={5}>5 (慢速，低内存)</Select.Option>
              <Select.Option value={10}>10 (推荐)</Select.Option>
              <Select.Option value={20}>20 (快速，高内存)</Select.Option>
              <Select.Option value={50}>50 (极速，极高内存)</Select.Option>
            </Select>
          </Form.Item>

          <div style={{ marginTop: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
            <Title level={5}>数据集信息</Title>
            <Space direction="vertical" size="small">
              <Text>样本数量: {selectedDataset?.num_samples}</Text>
              <Text>
                包含参考答案: {selectedDataset?.has_reference ? '是' : '否'}
              </Text>
              <Text>
                包含上下文: {selectedDataset?.has_contexts ? '是' : '否'}
              </Text>
            </Space>
          </div>

          <div style={{ marginTop: 16 }}>
            <Text type="secondary">
              提示：评测任务创建后将自动开始执行，请确保已正确配置 API 密钥。
            </Text>
          </div>
        </Form>
      </Modal>
    </div>
  );
};

export default Datasets;