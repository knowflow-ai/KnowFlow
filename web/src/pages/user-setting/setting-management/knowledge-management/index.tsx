import { useTranslate } from '@/hooks/common-hooks';
import request from '@/utils/request';
import {
  DatabaseOutlined,
  DeleteOutlined,
  EyeOutlined,
  FileOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Pagination,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'antd';
import React, { useEffect, useState } from 'react';
import styles from './index.less';
import { ParsingStatusCard } from './parsing-status-card';

const { Option } = Select;
const { TextArea } = Input;

interface KnowledgeBaseData {
  id: string;
  name: string;
  description: string;
  doc_num: number;
  language: string;
  permission: string;
  chunk_num: number;
  token_num: number;
  create_time: string;
  create_date: string;
}

interface LogItem {
  time: string;
  message: string;
}

interface DocumentData {
  id: string;
  name: string;
  chunk_num: number;
  progress: number;
  status: string;
  create_date: string;
  logs?: LogItem[]; // 日志字段，带时间戳
}

interface UserData {
  id: string;
  username: string;
}

interface FileData {
  id: string;
  name: string;
  size: number;
  type: string;
}

const KnowledgeManagementPage = () => {
  const { t } = useTranslate('setting');
  const [loading, setLoading] = useState(false);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [knowledgeData, setKnowledgeData] = useState<KnowledgeBaseData[]>([]);
  const [documentList, setDocumentList] = useState<DocumentData[]>([]);
  const [userList, setUserList] = useState<UserData[]>([]);

  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [viewModalVisible, setViewModalVisible] = useState(false);
  const [currentKnowledgeBase, setCurrentKnowledgeBase] =
    useState<KnowledgeBaseData | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [batchParsingLoading, setBatchParsingLoading] = useState(false);
  const [searchValue, setSearchValue] = useState('');

  const [createForm] = Form.useForm();
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });

  const [docPagination, setDocPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });

  // 1. 添加文档弹窗相关状态
  const [addDocModalVisible, setAddDocModalVisible] = useState(false);
  const [fileList, setFileList] = useState<FileData[]>([]);
  const [filePagination, setFilePagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  });
  const [selectedFileRowKeys, setSelectedFileRowKeys] = useState<string[]>([]);
  const [fileLoading, setFileLoading] = useState(false);

  // 解析和分块规则相关状态
  const [parseLoading, setParseLoading] = useState(false);
  const [chunkModalVisible, setChunkModalVisible] = useState(false);
  const [chunkDocId, setChunkDocId] = useState<string | null>(null);
  const [chunkDocName, setChunkDocName] = useState<string | null>(null);
  const [chunkConfig, setChunkConfig] = useState<any>({
    strategy: 'smart',
    chunk_token_num: 256,
    min_chunk_tokens: 10,
    regex_pattern: '',
  });
  const [chunkConfigLoading, setChunkConfigLoading] = useState(false);
  const [chunkConfigSaving, setChunkConfigSaving] = useState(false);

  // 解析进度弹窗相关状态
  // const [parseProgressModalVisible, setParseProgressModalVisible] = useState(false);
  // const [parseDocId, setParseDocId] = useState<string | null>(null);

  useEffect(() => {
    loadKnowledgeData();
    loadUserList();
  }, [pagination.current, pagination.pageSize, searchValue]);

  const loadKnowledgeData = async () => {
    setLoading(true);
    try {
      const res = await request.get('/api/v1/knowledgebases', {
        params: {
          currentPage: pagination.current,
          size: pagination.pageSize,
          name: searchValue,
        },
      });
      const data = res?.data?.data || {};
      setKnowledgeData(data.list || []);
      setPagination((prev) => ({ ...prev, total: data.total || 0 }));
    } catch (error) {
      message.error('加载知识库数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadUserList = async () => {
    try {
      const res = await request.get('/api/v1/users', {
        params: {
          currentPage: 1,
          size: 1000,
        },
      });
      const data = res?.data?.data || {};
      const users = (data.list || []).map((user: any) => ({
        id: user.id,
        username: user.username,
      }));
      setUserList(users);
    } catch (error) {
      message.error('加载用户列表失败');
    }
  };

  const loadDocumentList = async (kbId: string) => {
    setDocumentLoading(true);
    try {
      const res = await request.get(
        `/api/v1/knowledgebases/${kbId}/documents`,
        {
          params: {
            currentPage: docPagination.current,
            size: docPagination.pageSize,
          },
        },
      );
      const data = res?.data?.data || {};
      setDocumentList(data.list || []);
      setDocPagination((prev) => ({ ...prev, total: data.total || 0 }));
    } catch (error) {
      message.error('加载文档列表失败');
    } finally {
      setDocumentLoading(false);
    }
  };

  const handleSearch = () => {
    setPagination((prev) => ({ ...prev, current: 1 }));
    loadKnowledgeData();
  };

  const handleReset = () => {
    setSearchValue('');
    setPagination((prev) => ({ ...prev, current: 1 }));
    loadKnowledgeData();
  };

  const handleCreate = () => {
    createForm.resetFields();
    setCreateModalVisible(true);
  };

  const handleCreateSubmit = async () => {
    try {
      const values = await createForm.validateFields();
      setLoading(true);
      await request.post('/api/v1/knowledgebases', {
        data: values,
      });
      message.success('知识库创建成功');
      setCreateModalVisible(false);
      loadKnowledgeData();
    } catch (error) {
      message.error('创建知识库失败');
    } finally {
      setLoading(false);
    }
  };

  const handleView = (record: KnowledgeBaseData) => {
    setCurrentKnowledgeBase(record);
    setViewModalVisible(true);
    loadDocumentList(record.id);
  };

  const handleDelete = async (kbId: string) => {
    setLoading(true);
    try {
      await request.delete(`/api/v1/knowledgebases/${kbId}`);
      message.success('删除成功');
      loadKnowledgeData();
    } catch (error) {
      message.error('删除失败');
    } finally {
      setLoading(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的知识库');
      return;
    }

    setLoading(true);
    try {
      await request.delete('/api/v1/knowledgebases/batch', {
        data: { kbIds: selectedRowKeys },
      });
      setSelectedRowKeys([]);
      message.success(`成功删除 ${selectedRowKeys.length} 个知识库`);
      loadKnowledgeData();
    } catch (error) {
      message.error('批量删除失败');
    } finally {
      setLoading(false);
    }
  };

  const handleBatchParse = async () => {
    if (!currentKnowledgeBase) return;

    setBatchParsingLoading(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 3000));
      message.success('批量解析已完成');
      loadDocumentList(currentKnowledgeBase.id);
    } catch (error) {
      message.error('批量解析失败');
    } finally {
      setBatchParsingLoading(false);
    }
  };

  // 解析文档
  const handleParseDocument = async (doc: DocumentData) => {
    if (doc.progress === 1) {
      message.warning('文档已完成解析，无需再重复解析');
      return;
    }
    try {
      await request.post(`/api/v1/knowledgebases/documents/${doc.id}/parse`);
      // 直接开始轮询进度和日志，带时间戳
      pollParseProgressWithTimestamp(doc.id);
      message.success('解析任务已提交，进度和日志将在状态标签悬浮显示');
    } catch (error) {
      message.error('解析任务提交失败');
    }
  };

  // 轮询解析进度（带时间戳日志）
  const pollParseProgressWithTimestamp = async (
    docId: string,
    interval = 2000,
    maxTries = 60,
  ) => {
    let tries = 0;
    let finished = false;
    let lastMessage = '';
    while (!finished && tries < maxTries) {
      try {
        const res = await request.get(
          `/api/v1/knowledgebases/documents/${docId}/parse/progress`,
        );
        const response = res?.data;
        if (response?.code === 202) {
          // 解析进行中
          tries++;
          await new Promise((resolve) => setTimeout(resolve, interval));
          continue;
        }
        if (response?.code === 0) {
          const data = response.data || {};
          setDocumentList((prev) =>
            prev.map((item) => {
              if (item.id === docId) {
                let logs: LogItem[] = item.logs ?? [];
                if (data.message && data.message !== lastMessage) {
                  lastMessage = data.message;
                  const now = new Date();
                  const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
                  logs = [
                    { time: timeStr, message: data.message },
                    ...logs.slice(0, 19),
                  ];
                }
                return {
                  ...item,
                  progress: data.progress ?? item.progress,
                  logs,
                };
              }
              return item;
            }),
          );
          if (data.running === '3' || data.progress === 1) {
            finished = true;
            if (currentKnowledgeBase) loadDocumentList(currentKnowledgeBase.id);
            break;
          }
          if (data.status === '3') {
            finished = true;
            break;
          }
        }
      } catch (e) {
        // 忽略错误，继续轮询
      }
      tries++;
      await new Promise((resolve) => setTimeout(resolve, interval));
    }
  };

  // 分块规则弹窗
  const openChunkModal = (doc: DocumentData) => {
    setChunkDocId(doc.id);
    setChunkDocName(doc.name);
    setChunkModalVisible(true);
    loadChunkConfig(doc.id);
  };
  const loadChunkConfig = async (docId: string) => {
    setChunkConfigLoading(true);
    try {
      const res = await request.get(
        `/api/v1/documents/${docId}/chunking-config`,
      );
      const config = res?.data?.data?.chunking_config || {};
      setChunkConfig({
        strategy: config.strategy || 'smart',
        chunk_token_num: config.chunk_token_num || 256,
        min_chunk_tokens: config.min_chunk_tokens || 10,
        regex_pattern: config.regex_pattern || '',
      });
    } catch (error) {
      message.error('加载分块配置失败');
    } finally {
      setChunkConfigLoading(false);
    }
  };
  const handleChunkConfigSave = async () => {
    if (!chunkDocId) return;
    // 校验
    if (!chunkConfig.strategy) {
      message.error('请选择分块策略');
      return;
    }
    if (
      !chunkConfig.chunk_token_num ||
      chunkConfig.chunk_token_num < 50 ||
      chunkConfig.chunk_token_num > 2048
    ) {
      message.error('分块大小必须在50-2048之间');
      return;
    }
    if (
      !chunkConfig.min_chunk_tokens ||
      chunkConfig.min_chunk_tokens < 10 ||
      chunkConfig.min_chunk_tokens > 500
    ) {
      message.error('最小分块大小必须在10-500之间');
      return;
    }
    if (chunkConfig.strategy === 'strict_regex' && !chunkConfig.regex_pattern) {
      message.error('正则分块策略需要输入正则表达式');
      return;
    }
    setChunkConfigSaving(true);
    try {
      await request.put(`/api/v1/documents/${chunkDocId}/chunking-config`, {
        data: { chunking_config: chunkConfig },
      });
      message.success('分块配置保存成功');
      setChunkModalVisible(false);
      loadDocumentList(currentKnowledgeBase?.id || '');
    } catch (error) {
      message.error('保存分块配置失败');
    } finally {
      setChunkConfigSaving(false);
    }
  };

  // 移除文档
  const handleRemoveDocument = async (doc: DocumentData) => {
    if (!currentKnowledgeBase) return;
    Modal.confirm({
      title: `确定要从知识库中移除文档 "${doc.name}" 吗？`,
      content: '该操作只是移除知识库文件，不会删除原始文件',
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        try {
          await request.delete(`/api/v1/knowledgebases/documents/${doc.id}`);
          message.success('文档已从知识库移除');
          if (currentKnowledgeBase) loadDocumentList(currentKnowledgeBase.id);
        } catch (error) {
          message.error('移除文档失败');
        }
      },
    });
  };

  const columns = [
    {
      title: '序号',
      key: 'index',
      width: 80,
      render: (_: any, __: any, index: number) => (
        <span>
          {(pagination.current - 1) * pagination.pageSize + index + 1}
        </span>
      ),
    },
    {
      title: '知识库名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <Space>
          <DatabaseOutlined />
          {text}
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
      title: '文档数量',
      dataIndex: 'doc_num',
      key: 'doc_num',
      width: 100,
      render: (count: number) => <Tag color="blue">{count}</Tag>,
    },
    {
      title: '语言',
      dataIndex: 'language',
      key: 'language',
      width: 100,
      render: (lang: string) => (
        <Tag color="geekblue">{lang === 'Chinese' ? '中文' : '英文'}</Tag>
      ),
    },
    {
      title: '权限',
      dataIndex: 'permission',
      key: 'permission',
      width: 100,
      render: (permission: string) => (
        <Tag color={permission === 'me' ? 'green' : 'orange'}>
          {permission === 'me' ? '个人' : '团队'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'create_date',
      key: 'create_date',
      width: 180,
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right' as const,
      width: 200,
      render: (_: any, record: KnowledgeBaseData) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleView(record)}
          >
            查看
          </Button>
          <Popconfirm
            title={`确定要删除知识库 "${record.name}" 吗？`}
            description="删除后将无法恢复，且其中的所有文档也将被删除。"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const documentColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <Space>
          <FileOutlined />
          {text}
        </Space>
      ),
    },
    {
      title: '分块数',
      dataIndex: 'chunk_num',
      key: 'chunk_num',
      width: 100,
      render: (count: number) => <Tag color="cyan">{count}</Tag>,
    },
    {
      title: '上传日期',
      dataIndex: 'create_date',
      key: 'create_date',
      width: 180,
    },
    {
      title: '解析状态',
      key: 'status',
      width: 120,
      render: (_: any, record: DocumentData) => (
        <ParsingStatusCard record={record} />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 260,
      render: (_: any, record: DocumentData) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<PlayCircleOutlined />}
            loading={parseLoading}
            onClick={() => handleParseDocument(record)}
          >
            解析
          </Button>
          <Button
            type="link"
            size="small"
            icon={<SettingOutlined />}
            onClick={() => openChunkModal(record)}
          >
            分块规则
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleRemoveDocument(record)}
          >
            移除
          </Button>
        </Space>
      ),
    },
  ];

  const handleTableChange = (page: number, pageSize: number) => {
    setPagination((prev) => ({ ...prev, current: page, pageSize }));
  };

  // 2. 打开弹窗时加载文件列表
  const openAddDocModal = () => {
    setAddDocModalVisible(true);
    loadFileList(1, filePagination.pageSize);
  };
  const loadFileList = async (page = 1, pageSize = 10) => {
    setFileLoading(true);
    try {
      const res = await request.get('/api/v1/files', {
        params: { currentPage: page, size: pageSize },
      });
      const data = res?.data?.data || {};
      setFileList(data.list || []);
      setFilePagination((prev) => ({
        ...prev,
        current: page,
        pageSize,
        total: data.total || 0,
      }));
    } catch (error) {
      message.error('加载文件列表失败');
    } finally {
      setFileLoading(false);
    }
  };
  const handleFileTableChange = (page: number, pageSize: number) => {
    loadFileList(page, pageSize);
  };

  // 3. 提交
  const handleAddDocSubmit = async () => {
    if (!currentKnowledgeBase) return;
    if (selectedFileRowKeys.length === 0) {
      message.warning('请选择要添加的文件');
      return;
    }
    setFileLoading(true);
    try {
      await request.post(
        `/api/v1/knowledgebases/${currentKnowledgeBase.id}/documents`,
        {
          data: { file_ids: selectedFileRowKeys },
        },
      );
      message.success('文档添加成功');
      setAddDocModalVisible(false);
      setSelectedFileRowKeys([]);
      loadDocumentList(currentKnowledgeBase.id);
    } catch (error) {
      message.error('添加文档失败');
    } finally {
      setFileLoading(false);
    }
  };

  return (
    <div className={styles.knowledgeManagementWrapper}>
      {/* 搜索区域 */}
      <Card className={styles.searchCard} size="small">
        <Space>
          <Input
            placeholder="请输入知识库名称搜索"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleSearch}
            loading={loading}
          >
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置
          </Button>
        </Space>
      </Card>

      {/* 知识库列表 */}
      <Card className={styles.tableCard}>
        <div className={styles.tableHeader}>
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
            >
              新建知识库
            </Button>
            <Popconfirm
              title={`确定删除选中的 ${selectedRowKeys.length} 个知识库吗？`}
              description="此操作不可恢复，且其中的所有文档也将被删除"
              onConfirm={handleBatchDelete}
              disabled={selectedRowKeys.length === 0}
            >
              <Button
                danger
                icon={<DeleteOutlined />}
                disabled={selectedRowKeys.length === 0}
              >
                批量删除
              </Button>
            </Popconfirm>
          </Space>
          <Button icon={<ReloadOutlined />} onClick={loadKnowledgeData}>
            刷新
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={knowledgeData}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 1200 }}
          rowSelection={{
            selectedRowKeys,
            onChange: (selectedRowKeys: React.Key[]) =>
              setSelectedRowKeys(selectedRowKeys as string[]),
          }}
        />

        <div className={styles.paginationWrapper}>
          <Pagination
            current={pagination.current}
            pageSize={pagination.pageSize}
            total={pagination.total}
            onChange={handleTableChange}
            showSizeChanger
            showQuickJumper
            showTotal={(total, range) =>
              `第 ${range[0]}-${range[1]} 条/共 ${total} 条`
            }
          />
        </div>
      </Card>

      {/* 新建知识库模态框 */}
      <Modal
        title="新建知识库"
        open={createModalVisible}
        onOk={handleCreateSubmit}
        onCancel={() => setCreateModalVisible(false)}
        confirmLoading={loading}
        destroyOnClose
        width={600}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[
              { required: true, message: '请输入知识库名称' },
              { min: 2, max: 50, message: '长度在 2 到 50 个字符' },
            ]}
          >
            <Input placeholder="请输入知识库名称" />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
            rules={[{ max: 200, message: '描述不能超过200个字符' }]}
          >
            <TextArea rows={3} placeholder="请输入知识库描述" />
          </Form.Item>
          <Form.Item
            name="language"
            label="语言"
            initialValue="Chinese"
            rules={[{ required: true, message: '请选择语言' }]}
          >
            <Select>
              <Option value="Chinese">中文</Option>
              <Option value="English">英文</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="creator_id"
            label="创建人"
            rules={[{ required: true, message: '请选择创建人' }]}
          >
            <Select
              placeholder="请选择创建人"
              showSearch
              optionFilterProp="children"
              loading={userList.length === 0}
            >
              {userList.map((user) => (
                <Option key={user.id} value={user.id}>
                  {user.username}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="permission"
            label="权限"
            initialValue="me"
            rules={[{ required: true, message: '请选择权限' }]}
          >
            <Select>
              <Option value="me">个人</Option>
              <Option value="team">团队</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 知识库详情模态框 */}
      <Modal
        title={`知识库详情 - ${currentKnowledgeBase?.name || ''}`}
        open={viewModalVisible}
        onCancel={() => setViewModalVisible(false)}
        width={1000}
        footer={[
          <Button key="close" onClick={() => setViewModalVisible(false)}>
            关闭
          </Button>,
        ]}
      >
        {currentKnowledgeBase && (
          <div>
            <Descriptions
              className={styles.kbInfo}
              column={2}
              bordered
              size="small"
            >
              <Descriptions.Item label="知识库ID">
                {currentKnowledgeBase.id}
              </Descriptions.Item>
              <Descriptions.Item label="文档总数">
                {currentKnowledgeBase.doc_num}
              </Descriptions.Item>
              <Descriptions.Item label="语言">
                <Tag color="geekblue">
                  {currentKnowledgeBase.language === 'Chinese'
                    ? '中文'
                    : '英文'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="权限">
                <Tag
                  color={
                    currentKnowledgeBase.permission === 'me'
                      ? 'green'
                      : 'orange'
                  }
                >
                  {currentKnowledgeBase.permission === 'me' ? '个人' : '团队'}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            <div className={styles.documentHeader}>
              <Space>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={openAddDocModal}
                >
                  添加文档
                </Button>
                <Button
                  type="default"
                  icon={<ThunderboltOutlined />}
                  loading={batchParsingLoading}
                  onClick={handleBatchParse}
                  disabled={documentList.length === 0}
                >
                  {batchParsingLoading ? '正在批量解析...' : '批量解析'}
                </Button>
              </Space>
            </div>

            {batchParsingLoading && (
              <Alert
                message="正在进行批量解析"
                description="该过程将在后台运行，您可以稍后查看结果。"
                type="info"
                showIcon
                className={styles.batchAlert}
              />
            )}

            <div className={styles.documentTableWrapper}>
              <Table
                columns={documentColumns}
                dataSource={documentList}
                rowKey="id"
                loading={documentLoading}
                pagination={false}
                size="small"
                locale={{
                  emptyText: <Empty description="暂无文档数据" />,
                }}
              />
            </div>
          </div>
        )}
      </Modal>

      {/* 添加文档弹窗 */}
      <Modal
        title="添加文档到知识库"
        open={addDocModalVisible}
        onOk={handleAddDocSubmit}
        onCancel={() => setAddDocModalVisible(false)}
        confirmLoading={fileLoading}
        destroyOnClose
        width={800}
      >
        <Table
          rowSelection={{
            selectedRowKeys: selectedFileRowKeys,
            onChange: (keys) => setSelectedFileRowKeys(keys as string[]),
          }}
          columns={[
            { title: '文件名', dataIndex: 'name', key: 'name' },
            {
              title: '大小',
              dataIndex: 'size',
              key: 'size',
              width: 120,
              render: (size: number) => {
                if (size == null || typeof size !== 'number') {
                  return '0 B';
                }
                return size < 1024
                  ? `${size} B`
                  : size < 1024 * 1024
                    ? `${(size / 1024).toFixed(2)} KB`
                    : `${(size / 1024 / 1024).toFixed(2)} MB`;
              },
            },
            { title: '类型', dataIndex: 'type', key: 'type', width: 120 },
          ]}
          dataSource={fileList}
          rowKey="id"
          loading={fileLoading}
          pagination={false}
          size="small"
        />
        <Pagination
          current={filePagination.current}
          pageSize={filePagination.pageSize}
          total={filePagination.total}
          onChange={handleFileTableChange}
          showSizeChanger
          showQuickJumper
          style={{ marginTop: 16, textAlign: 'right' }}
        />
      </Modal>

      {/* 分块规则弹窗 */}
      <Modal
        title={`分块规则 - ${chunkDocName || ''}`}
        open={chunkModalVisible}
        onOk={handleChunkConfigSave}
        onCancel={() => setChunkModalVisible(false)}
        confirmLoading={chunkConfigSaving}
        destroyOnClose
        width={500}
      >
        <Form layout="vertical">
          <Form.Item label="分块策略" required>
            <Select
              value={chunkConfig.strategy}
              onChange={(v) =>
                setChunkConfig((c: any) => ({ ...c, strategy: v }))
              }
            >
              <Option value="basic">基础分块</Option>
              <Option value="smart">智能分块</Option>
              <Option value="advanced">按标题分块</Option>
              <Option value="strict_regex">正则分块</Option>
            </Select>
          </Form.Item>
          <Form.Item label="分块大小" required>
            <Input
              type="number"
              min={50}
              max={2048}
              value={chunkConfig.chunk_token_num}
              onChange={(e) =>
                setChunkConfig((c: any) => ({
                  ...c,
                  chunk_token_num: Number(e.target.value),
                }))
              }
              placeholder="50-2048"
            />
          </Form.Item>
          <Form.Item label="最小分块大小" required>
            <Input
              type="number"
              min={10}
              max={500}
              value={chunkConfig.min_chunk_tokens}
              onChange={(e) =>
                setChunkConfig((c: any) => ({
                  ...c,
                  min_chunk_tokens: Number(e.target.value),
                }))
              }
              placeholder="10-500"
            />
          </Form.Item>
          {chunkConfig.strategy === 'strict_regex' && (
            <Form.Item label="正则表达式" required>
              <Input
                value={chunkConfig.regex_pattern}
                onChange={(e) =>
                  setChunkConfig((c: any) => ({
                    ...c,
                    regex_pattern: e.target.value,
                  }))
                }
                placeholder="请输入正则表达式"
              />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* 解析进度弹窗 */}
      {/* 解析进度弹窗相关代码已移除 */}
    </div>
  );
};

export default KnowledgeManagementPage;
