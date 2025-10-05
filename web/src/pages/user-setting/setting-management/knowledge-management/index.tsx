import { useTranslate } from '@/hooks/common-hooks';
import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
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
  UserOutlined,
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
import React, { useEffect, useRef, useState } from 'react';
import {
  BatchParseMonitor,
  startBatchParsing,
  type BatchParsingState,
  type DocumentProgress,
} from './batch-parse-helper';
import styles from './index.less';
import ParseConfigModal from './parse-config-modal';
import { ParsingStatusCard } from './parsing-status-card';
import PermissionModal from './permission-modal';

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
  created_by: string;
  parser_id?: string;
  permission_stats?: {
    user_count: number;
    team_count: number;
    total_count: number;
  };
  creator_name?: string;
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
  parser_id?: string; // 分块方法
  parser_config?: {
    layout_recognize?: string; // PDF 解析器
    chunk_token_num?: number; // 分块大小
    [key: string]: any;
  };
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
  const [permissionModalVisible, setPermissionModalVisible] = useState(false);
  const [currentKnowledgeBase, setCurrentKnowledgeBase] =
    useState<KnowledgeBaseData | null>(null);

  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [selectedDocumentKeys, setSelectedDocumentKeys] = useState<string[]>(
    [],
  );
  const [batchParseSelectionMode, setBatchParseSelectionMode] = useState(false);
  const [searchValue, setSearchValue] = useState('');

  // 批量解析状态和监控器
  const [batchParsingStatus, setBatchParsingStatus] = useState<{
    isActive: boolean;
    totalDocuments: number;
    completedDocuments: number;
    currentDocumentName: string | null;
    message: string;
    error: string | null;
    startTime: number | null;
  }>({
    isActive: false,
    totalDocuments: 0,
    completedDocuments: 0,
    currentDocumentName: null,
    message: '',
    error: null,
    startTime: null,
  });

  const batchMonitor = useRef<any>(null);

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

  // 文档搜索状态
  const [docSearchValue, setDocSearchValue] = useState('');

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
  const [parseLoadingMap, setParseLoadingMap] = useState<
    Record<string, boolean>
  >({});
  // 轮询定时器管理
  const [pollingTimers, setPollingTimers] = useState<
    Record<string, { timerId?: NodeJS.Timeout; isActive: boolean }>
  >({});
  // 解析配置对话框
  const [parseConfigModalVisible, setParseConfigModalVisible] = useState(false);
  const [currentParseDoc, setCurrentParseDoc] = useState<DocumentData | null>(
    null,
  );

  // 管理单个文档的解析状态
  const setDocumentParseLoading = (docId: string, loading: boolean) => {
    setParseLoadingMap((prev) => ({
      ...prev,
      [docId]: loading,
    }));
  };

  const isDocumentParsing = (docId: string) => {
    return parseLoadingMap[docId] || false;
  };

  // 管理轮询定时器
  const setPollingTimer = (
    docId: string,
    timerId?: NodeJS.Timeout,
    isActive: boolean = true,
  ) => {
    setPollingTimers((prev) => ({
      ...prev,
      [docId]: { timerId, isActive },
    }));
  };

  const clearPollingTimer = (docId: string) => {
    const timer = pollingTimers[docId];
    if (timer?.timerId) {
      clearTimeout(timer.timerId);
    }
    if (timer?.isActive) {
      setPollingTimers((prev) => {
        const newTimers = { ...prev };
        delete newTimers[docId];
        return newTimers;
      });
    }
  };

  const isPollingActive = (docId: string) => {
    return pollingTimers[docId]?.isActive || false;
  };
  const [chunkModalVisible, setChunkModalVisible] = useState(false);
  const [chunkDocId, setChunkDocId] = useState<string | null>(null);
  const [chunkDocName, setChunkDocName] = useState<string | null>(null);
  const [chunkConfig, setChunkConfig] = useState<any>({
    strategy: 'smart',
    chunk_token_num: 256,
    min_chunk_tokens: 10,
    regex_pattern: '',
    parent_config: {
      parent_chunk_size: 1024,
      parent_chunk_overlap: 100,
      parent_split_level: 2,
      retrieval_mode: 'parent',
    },
  });
  const [chunkConfigLoading, setChunkConfigLoading] = useState(false);
  const [chunkConfigSaving, setChunkConfigSaving] = useState(false);

  // 登录用户信息
  const { data: userInfo } = useFetchUserInfo();
  const userId = userInfo?.id;

  // 角色管理相关函数
  const handleOpenPermissionModal = async (record: KnowledgeBaseData) => {
    if (!userId) return;
    setCurrentKnowledgeBase(record);
    setPermissionModalVisible(true);
  };

  // 解析进度弹窗相关状态
  // const [parseProgressModalVisible, setParseProgressModalVisible] = useState(false);
  // const [parseDocId, setParseDocId] = useState<string | null>(null);

  // 初始化时先加载用户列表，再加载知识库数据
  useEffect(() => {
    const initData = async () => {
      await loadUserList();
      await loadKnowledgeData();
    };
    initData();
  }, []);

  // 当分页或搜索条件变化时，只重新加载知识库数据
  useEffect(() => {
    if (userList.length > 0) {
      loadKnowledgeData();
    }
  }, [pagination.current, pagination.pageSize, searchValue, userList]);

  // 监听文档分页变化
  useEffect(() => {
    if (currentKnowledgeBase?.id) {
      loadDocumentList(currentKnowledgeBase.id);
    }
  }, [docPagination.current, docPagination.pageSize, docSearchValue]);

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      if (batchMonitor.current) {
        batchMonitor.current.stop();
      }
      // 清理所有文档轮询定时器
      Object.keys(pollingTimers).forEach((docId) => {
        const timer = pollingTimers[docId];
        if (timer?.timerId) {
          clearTimeout(timer.timerId);
        }
      });
    };
  }, [pollingTimers]);

  const loadKnowledgeData = async () => {
    setLoading(true);
    try {
      const res = await request.get('/api/knowflow/v1/knowledgebases', {
        params: {
          current_page: pagination.current, // 修正参数名
          size: pagination.pageSize,
          name: searchValue,
        },
      });
      const data = res?.data?.data || {};
      const knowledgeList = data.list || [];

      // Map creator IDs to creator names
      const enhancedList = knowledgeList.map((kb: KnowledgeBaseData) => {
        const creator = userList.find((user) => user.id === kb.created_by);
        return {
          ...kb,
          creator_name: creator?.username || kb.created_by,
        };
      });

      setKnowledgeData(enhancedList);
      setPagination((prev) => ({ ...prev, total: data.total || 0 }));
    } catch (error) {
      message.error('加载知识库数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadUserList = async () => {
    try {
      const res = await request.get('/api/knowflow/v1/users', {
        params: {
          current_page: 1, // 修正参数名
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
      const params = {
        current_page: docPagination.current, // 修正参数名
        size: docPagination.pageSize,
        name: docSearchValue, // 添加搜索参数
      };

      const res = await request.get(
        `/api/knowflow/v1/knowledgebases/${kbId}/documents`,
        { params },
      );
      const data = res?.data?.data || {};
      const documentList = data.list || [];
      setDocumentList(documentList);

      // 文档状态已通过批量解析系统统一管理，无需单独轮询
      setDocPagination((prev) => ({ ...prev, total: data.total || 0 }));
    } catch (error) {
      message.error('加载文档列表失败');
    } finally {
      setDocumentLoading(false);
    }
  };

  const handleSearch = () => {
    setPagination((prev) => ({ ...prev, current: 1 }));
    // loadKnowledgeData will be called automatically by useEffect when pagination changes
  };

  const handleReset = () => {
    setSearchValue('');
    setPagination((prev) => ({ ...prev, current: 1 }));
    // loadKnowledgeData will be called automatically by useEffect when pagination and searchValue change
  };

  const handleCreate = () => {
    createForm.resetFields();
    // 普通管理员默认设置创建人为当前用户，超级管理员可以选择
    if (!userInfo?.roles?.includes('super_admin')) {
      createForm.setFieldsValue({
        creator_id: userId,
      });
    }
    setCreateModalVisible(true);
  };

  const handleCreateSubmit = async () => {
    try {
      const values = await createForm.validateFields();
      setLoading(true);
      await request.post('/api/knowflow/v1/knowledgebases', {
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

  const handleView = async (record: KnowledgeBaseData) => {
    if (!userId) return;
    setCurrentKnowledgeBase(record);
    setViewModalVisible(true);
    // 重置文档搜索和分页
    setDocSearchValue('');
    setDocPagination({ current: 1, pageSize: 10, total: 0 });
    // 重置批量解析选择状态
    setBatchParseSelectionMode(false);
    setSelectedDocumentKeys([]);
    loadDocumentList(record.id);
  };

  // 文档搜索处理
  const handleDocSearch = () => {
    setDocPagination((prev) => ({ ...prev, current: 1 }));
    if (currentKnowledgeBase) {
      loadDocumentList(currentKnowledgeBase.id);
    }
  };

  const handleDocReset = () => {
    setDocSearchValue('');
    setDocPagination((prev) => ({ ...prev, current: 1 }));
    if (currentKnowledgeBase) {
      loadDocumentList(currentKnowledgeBase.id);
    }
  };

  const handleDelete = async (kbId: string) => {
    if (!userId) return;

    // 如果正在删除当前查看的知识库，停止批量解析监控
    if (currentKnowledgeBase?.id === kbId && batchParsingStatus.isActive) {
      stopBatchProgressMonitoring();
      message.info('已停止该知识库的批量解析任务');
    }

    setLoading(true);
    try {
      await request.delete(`/api/knowflow/v1/knowledgebases/${kbId}`);
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

    // 如果正在批量删除的知识库中包含当前查看的知识库，停止批量解析监控
    if (
      currentKnowledgeBase &&
      selectedRowKeys.includes(currentKnowledgeBase.id) &&
      batchParsingStatus.isActive
    ) {
      stopBatchProgressMonitoring();
      message.info('已停止相关知识库的批量解析任务');
    }

    setLoading(true);
    try {
      await request.delete('/api/knowflow/v1/knowledgebases/batch', {
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

  // 批量解析处理函数
  const handleBatchParse = async () => {
    if (!currentKnowledgeBase) return;

    if (!batchParseSelectionMode) {
      // 首次点击：进入选择模式，默认全选
      setBatchParseSelectionMode(true);
      const allDocumentIds = documentList.map((doc) => doc.id);
      setSelectedDocumentKeys(allDocumentIds);
      message.info('请勾选要解析的文档，然后点击"开始解析"');
    } else {
      // 二次点击：确认开始解析
      if (selectedDocumentKeys.length === 0) {
        message.warning('请至少选择一个文档进行解析');
        return;
      }
      await startSelectedDocumentsParsing();
    }
  };

  // 开始解析选中的文档
  const startSelectedDocumentsParsing = async () => {
    if (!currentKnowledgeBase) return;

    const kbId = currentKnowledgeBase.id;
    const kbName = currentKnowledgeBase.name;
    const selectedCount = selectedDocumentKeys.length;

    Modal.confirm({
      title: '启动批量解析确认',
      content: (
        <div>
          <p>
            确定要为知识库 "{kbName}" 的 {selectedCount} 个文档启动批量解析吗？
          </p>
          <p style={{ color: '#E6A23C', fontWeight: 'bold' }}>
            批量解析将按顺序处理选中的文档，请耐心等待完成。
          </p>
        </div>
      ),
      okText: '确定启动',
      cancelText: '取消',
      onOk: async () => {
        try {
          const success = await startBatchParsing(kbId, request);

          if (success) {
            message.success('批量解析任务已启动');
            // 开始监控进度
            startBatchProgressMonitoring(kbId);
            // 退出选择模式
            setBatchParseSelectionMode(false);
            setSelectedDocumentKeys([]);
          } else {
            message.error('启动批量解析失败');
          }
        } catch (error: any) {
          message.error(`启动批量解析时出错: ${error?.message || '网络错误'}`);
          console.error('启动批量解析失败:', error);
        }
      },
    });
  };

  // 取消批量解析选择模式
  const handleCancelBatchParse = () => {
    setBatchParseSelectionMode(false);
    setSelectedDocumentKeys([]);
    message.info('已取消批量解析选择');
  };

  // 开始批量解析进度监控
  const startBatchProgressMonitoring = (kbId: string) => {
    // 停止旧的监控器
    if (batchMonitor.current) {
      batchMonitor.current.stop();
    }

    // 创建新的监控器
    batchMonitor.current = new BatchParseMonitor(
      kbId,
      request,
      (state: BatchParsingState) => {
        setBatchParsingStatus(state);

        // 如果完成了，显示结果并刷新列表
        if (!state.isActive) {
          const isSuccess = !state.error;
          message[isSuccess ? 'success' : 'error'](state.message);

          // 刷新文档列表和知识库列表
          if (currentKnowledgeBase) {
            loadDocumentList(currentKnowledgeBase.id);
            loadKnowledgeData();
          }
        }
      },
      (documents: DocumentProgress[]) => {
        console.log(
          '[UI] 文档更新回调被调用，接收到文档数量:',
          documents.length,
        );
        console.log('[UI] 接收到的文档数据:', documents);

        // 更新文档列表状态，与批量解析进度联动
        setDocumentList((prevList) => {
          console.log('[UI] 当前文档列表长度:', prevList.length);

          const updatedList = prevList.map((doc) => {
            const updatedDoc = documents.find((d) => d.id === doc.id);
            if (updatedDoc) {
              console.log(`[UI] 更新文档: ${doc.name}`, {
                progress: `${doc.progress} -> ${updatedDoc.progress}`,
                chunk_num: `${doc.chunk_num} -> ${updatedDoc.chunk_num}`,
                run: `${doc.run} -> ${updatedDoc.run}`,
              });

              return {
                ...doc,
                progress: updatedDoc.progress,
                chunk_num: updatedDoc.chunk_num,
                run: updatedDoc.run,
                status: updatedDoc.status,
                // 如果有新的解析消息，添加到日志中
                logs:
                  updatedDoc.message &&
                  updatedDoc.message !== doc.logs?.[0]?.message
                    ? [
                        {
                          time: new Date().toLocaleTimeString(),
                          message: updatedDoc.message,
                        },
                        ...(doc.logs || []).slice(0, 19),
                      ]
                    : doc.logs,
              };
            }
            return doc;
          });

          console.log('[UI] 文档列表更新完成');
          return updatedList;
        });
      },
      // 传递当前分页信息
      {
        current: docPagination.current,
        pageSize: docPagination.pageSize,
      },
    );

    // 启动监控
    batchMonitor.current.start();
  };

  // 停止批量解析监控
  const stopBatchProgressMonitoring = () => {
    if (batchMonitor.current) {
      batchMonitor.current.stop();
      batchMonitor.current = null;
    }

    setBatchParsingStatus((prev) => ({
      ...prev,
      isActive: false,
    }));
  };

  // 解析文档 - 直接使用当前配置解析
  const handleParseDocument = async (doc: DocumentData) => {
    // 如果文档已完成解析，显示确认对话框
    if (doc.progress === 1) {
      Modal.confirm({
        title: '确认重新解析',
        content: (
          <div>
            <p>
              确定要重新解析文档 "<strong>{doc.name}</strong>" 吗？
            </p>
            <p style={{ color: '#ff4d4f', marginTop: 8 }}>
              注意：此操作会清空该文档的所有现有分块数据，分块数量将重置为
              0，然后重新开始解析过程。
            </p>
          </div>
        ),
        okText: '确认重新解析',
        cancelText: '取消',
        okType: 'danger',
        onOk: async () => {
          await performParse(doc);
        },
      });
    } else {
      // 未解析或解析中的文档直接解析
      await performParse(doc);
    }
  };

  // 执行解析的具体逻辑
  const performParse = async (
    doc: DocumentData,
    parseConfig?: {
      parser_id: string;
      layout_recognize: string;
      parser_config?: Record<string, any>;
    },
  ) => {
    try {
      // 设置解析状态为活跃
      setDocumentParseLoading(doc.id, true);

      // 立即重置前端显示的解析状态（无论文档之前是什么状态）
      setDocumentList((prevList) =>
        prevList.map((item) =>
          item.id === doc.id
            ? {
                ...item,
                chunk_num: 0,
                progress: 0,
                // 不手动设置 run，让后端返回的真实状态来更新
                logs: [
                  {
                    time: new Date().toLocaleTimeString('zh-CN', {
                      hour12: false,
                    }),
                    message: '提交解析任务...',
                  },
                ],
              }
            : item,
        ),
      );

      await request.post(
        `/api/knowflow/v1/knowledgebases/documents/${doc.id}/parse`,
        {
          data: parseConfig || {},
          headers: {
            'Content-Type': 'application/json',
          },
        },
      );

      // 开始轮询进度
      pollParseProgressWithTimestamp(doc.id);
      message.success(
        doc.progress === 1 ? '重新解析任务已提交' : '解析任务已提交',
      );
    } catch (error) {
      message.error(
        doc.progress === 1 ? '重新解析任务提交失败' : '解析任务提交失败',
      );
      // 出错时立即恢复按钮状态和清理定时器
      setDocumentParseLoading(doc.id, false);
      clearPollingTimer(doc.id);
    }
    // 注意：不在这里设置 loading 为 false，而是在轮询完成后设置
  };

  // 处理分块配置对话框的确认 - 只保存配置，不触发解析
  const handleParseConfigOk = async (values: {
    parser_id: string;
    layout_recognize: string;
    parser_config?: Record<string, any>;
  }) => {
    if (!currentParseDoc) return;

    try {
      // 调用后端保存配置
      await request.post(
        `/api/knowflow/v1/knowledgebases/documents/${currentParseDoc.id}/update-parser-config`,
        {
          data: {
            parser_id: values.parser_id,
            layout_recognize: values.layout_recognize,
            parser_config: values.parser_config,
          },
          headers: {
            'Content-Type': 'application/json',
          },
        },
      );

      message.success('分块配置已保存');
      setParseConfigModalVisible(false);

      // 刷新文档列表以显示更新后的配置
      loadDocumentList(currentKnowledgeBase?.id || '');
    } catch (error) {
      message.error('保存配置失败');
    }
  };

  // 简化的轮询解析进度
  const pollParseProgressWithTimestamp = async (docId: string) => {
    let polling = true;
    let tries = 0;
    const maxTries = 60;
    const interval = 2000;

    console.log(
      `[DEBUG] 单文档轮询开始 - docId: ${docId}, maxTries: ${maxTries}, interval: ${interval}ms`,
    );

    const poll = async () => {
      console.log(
        `[DEBUG] 单文档轮询执行 - docId: ${docId}, tries: ${tries}, polling: ${polling}`,
      );

      if (!polling || tries >= maxTries) {
        // 超时或被停止，清理状态
        console.log(
          `[DEBUG] 单文档轮询停止 - docId: ${docId}, reason: ${!polling ? 'polling=false' : 'max tries reached'}, tries: ${tries}`,
        );
        setDocumentParseLoading(docId, false);
        clearPollingTimer(docId);
        return;
      }

      tries++;

      try {
        const res = await request.get(
          `/api/knowflow/v1/knowledgebases/documents/${docId}/parse/progress`,
        );
        const response = res?.data;

        if (response?.code === 0) {
          const data = response.data || {};

          // 更新文档状态
          setDocumentList((prev) => {
            return prev.map((item) => {
              if (item.id === docId) {
                let logs: LogItem[] = item.logs ?? [];
                if (data.progress_msg) {
                  const now = new Date();
                  const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
                  logs = [
                    { time: timeStr, message: data.progress_msg },
                    ...logs.slice(0, 19),
                  ];
                }
                return {
                  ...item,
                  progress: data.progress ?? item.progress,
                  chunk_num: data.chunk_num ?? item.chunk_num,
                  run: data.run ?? item.run,
                  logs,
                };
              }
              return item;
            });
          });

          // 检查是否完成（run='3' 表示已完成，progress=1 表示100%）
          if (data.run === '3' || data.progress === 1) {
            console.log(
              `[解析完成] docId=${docId}, run=${data.run}, progress=${data.progress}, chunk_num=${data.chunk_num}`,
            );
            polling = false;
            setDocumentParseLoading(docId, false);
            console.log(`[解析完成] 已清理parseLoadingMap - docId=${docId}`);
            clearPollingTimer(docId);

            // 如果 chunk_num 为 0，说明 RAGFlow 还没更新完，延迟 2 秒后再查询一次
            if (data.chunk_num === 0) {
              setTimeout(async () => {
                try {
                  const finalRes = await request.get(
                    `/api/knowflow/v1/knowledgebases/documents/${docId}/parse/progress`,
                  );
                  const finalData = finalRes?.data?.data || {};

                  setDocumentList((prev) =>
                    prev.map((item) =>
                      item.id === docId
                        ? {
                            ...item,
                            chunk_num: finalData.chunk_num ?? item.chunk_num,
                            run: finalData.run ?? item.run,
                          }
                        : item,
                    ),
                  );
                  loadKnowledgeData();
                } catch (error) {
                  console.error('延迟查询chunk_num失败:', error);
                  loadKnowledgeData();
                }
              }, 1500);
            } else {
              // chunk_num 已有值，直接刷新
              loadKnowledgeData();
            }

            return;
          }
        }

        // 继续轮询
        if (polling) {
          console.log(
            `[DEBUG] 单文档轮询继续 - docId: ${docId}, 下次执行间隔: ${interval}ms`,
          );
          const timerId = setTimeout(poll, interval);
          setPollingTimer(docId, timerId, true);
        }
      } catch (error) {
        console.log(
          `[DEBUG] 单文档轮询API错误 - docId: ${docId}, error:`,
          error,
        );
        // 出错也继续轮询
        if (polling) {
          console.log(`[DEBUG] 单文档轮询错误后继续 - docId: ${docId}`);
          const timerId = setTimeout(poll, interval);
          setPollingTimer(docId, timerId, true);
        }
      }
    };

    // 开始轮询
    console.log(`[DEBUG] 单文档轮询初始化完成，开始执行 - docId: ${docId}`);
    setPollingTimer(docId, undefined, true);
    poll();

    // 返回停止函数
    return () => {
      console.log(`[DEBUG] 单文档轮询手动停止 - docId: ${docId}`);
      polling = false;
      clearPollingTimer(docId);
    };
  };

  // 分块规则弹窗 - 使用新的 ParseConfigModal
  const openChunkModal = (doc: DocumentData) => {
    setCurrentParseDoc(doc);
    setParseConfigModalVisible(true);
  };
  const loadChunkConfig = async (docId: string) => {
    setChunkConfigLoading(true);
    try {
      const res = await request.get(
        `/api/knowflow/v1/documents/${docId}/chunking-config`,
      );
      const config = res?.data?.data?.chunking_config || {};
      setChunkConfig({
        strategy: config.strategy || 'smart',
        chunk_token_num: config.chunk_token_num || 256,
        min_chunk_tokens: config.min_chunk_tokens || 10,
        regex_pattern: config.regex_pattern || '',
        parent_config: config.parent_config || {
          parent_chunk_size: 1024,
          parent_chunk_overlap: 100,
          parent_split_level: 2,
          retrieval_mode: 'parent',
        },
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
    if (chunkConfig.strategy === 'parent_child') {
      const parentConfig = chunkConfig.parent_config;
      if (!parentConfig) {
        message.error('父子分块策略需要配置父分块参数');
        return;
      }
      if (
        !parentConfig.parent_chunk_size ||
        parentConfig.parent_chunk_size < 200 ||
        parentConfig.parent_chunk_size > 4000
      ) {
        message.error('父分块大小必须在200-4000之间');
        return;
      }
      if (
        parentConfig.parent_chunk_overlap < 0 ||
        parentConfig.parent_chunk_overlap > 512
      ) {
        message.error('父分块重叠大小必须在0-512之间');
        return;
      }
      if (
        !parentConfig.parent_split_level ||
        parentConfig.parent_split_level < 1 ||
        parentConfig.parent_split_level > 6
      ) {
        message.error('父分块分割级别必须在1-6之间');
        return;
      }
      if (!parentConfig.retrieval_mode) {
        message.error('请选择检索模式');
        return;
      }
    }
    setChunkConfigSaving(true);
    try {
      await request.put(
        `/api/knowflow/v1/documents/${chunkDocId}/chunking-config`,
        {
          data: { chunking_config: chunkConfig },
        },
      );
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
          // 清理文档对应的轮询定时器
          clearPollingTimer(doc.id);
          // 清理解析状态
          setDocumentParseLoading(doc.id, false);

          await request.delete(
            `/api/knowflow/v1/knowledgebases/documents/${doc.id}`,
          );
          message.success('文档已从知识库移除');

          // 刷新文档列表
          if (currentKnowledgeBase) {
            loadDocumentList(currentKnowledgeBase.id);

            // 文档删除后，批量解析状态会自动更新，无需手动刷新
          }
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
      width: 60,
      align: 'left',
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
      width: 200,
      align: 'left',
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
      width: 180,
      align: 'left',
      ellipsis: true,
    },
    {
      title: '创建人',
      dataIndex: 'creator_name',
      key: 'creator_name',
      width: 100,
      align: 'left',
      render: (name: string, record: KnowledgeBaseData) => (
        <span>{name || record.created_by}</span>
      ),
    },
    {
      title: '文档',
      dataIndex: 'doc_num',
      key: 'doc_num',
      width: 80,
      align: 'left',
      render: (count: number) => <Tag color="blue">{count}</Tag>,
    },
    {
      title: '角色配置',
      dataIndex: 'permission_stats',
      key: 'permission_stats',
      width: 100,
      align: 'left',
      render: (
        stats:
          | { user_count: number; team_count: number; total_count: number }
          | undefined,
      ) => {
        if (!stats || stats.total_count === 0) {
          return <Tag color="gray">未配置</Tag>;
        }

        const parts = [];
        if (stats.user_count > 0) {
          parts.push(`${stats.user_count}用户`);
        }
        if (stats.team_count > 0) {
          parts.push(`${stats.team_count}团队`);
        }

        return (
          <Tag
            color="blue"
            title={`角色分配详情：\n• ${stats.user_count}个直接用户角色\n• ${stats.team_count}个团队角色（影响团队内所有成员）\n• 点击"角色"按钮查看详细配置`}
          >
            {parts.join(' ')}
          </Tag>
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'create_date',
      key: 'create_date',
      width: 150,
      align: 'left',
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right' as const,
      width: 220,
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
          <Button
            type="link"
            size="small"
            icon={<UserOutlined />}
            onClick={() => handleOpenPermissionModal(record)}
          >
            角色
          </Button>
          <Popconfirm
            title="确定删除该知识库吗？"
            description="此操作不可恢复，且其中的所有文档也将被删除"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleDelete(record.id)}
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
        <ParsingStatusCard
          record={record}
          isBatchParsing={batchParsingStatus.isActive}
          currentBatchDocument={batchParsingStatus.currentDocumentName}
        />
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
            icon={
              record.progress === 1 ? (
                <ReloadOutlined />
              ) : (
                <PlayCircleOutlined />
              )
            }
            loading={isDocumentParsing(record.id)}
            disabled={
              isDocumentParsing(record.id) ||
              (record.run === '1' && record.progress !== 1)
            }
            onClick={() => {
              console.log(
                `[按钮点击] docId=${record.id}, isParsing=${isDocumentParsing(record.id)}, run=${record.run}, progress=${record.progress}`,
              );
              handleParseDocument(record);
            }}
          >
            {record.progress === 1 ? '重新解析' : '解析'}
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
      const res = await request.get('/api/knowflow/v1/files', {
        params: { current_page: page, size: pageSize }, // 修正参数名
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
        `/api/knowflow/v1/knowledgebases/${currentKnowledgeBase.id}/documents`,
        {
          data: { file_ids: selectedFileRowKeys },
        },
      );
      message.success('文档添加成功');
      setAddDocModalVisible(false);
      setSelectedFileRowKeys([]);
      // 刷新文档列表和知识库列表（更新文档数量）
      loadDocumentList(currentKnowledgeBase.id);
      loadKnowledgeData();
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
          scroll={{ x: 1100 }}
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
            {userInfo?.is_superuser ? (
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
            ) : (
              <Select
                value={userId}
                disabled
                style={{ backgroundColor: '#f5f5f5' }}
              >
                <Option value={userId}>
                  {userInfo?.nickname || '当前管理员'}
                </Option>
              </Select>
            )}
          </Form.Item>
          <Form.Item
            name="permission"
            label="可见范围"
            initialValue="me"
            rules={[{ required: true, message: '请选择可见范围' }]}
          >
            <Select>
              <Option value="me">个人</Option>
              <Option value="team">团队</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="parser_id"
            label="解析方法"
            initialValue="mineru"
            rules={[{ required: true, message: '请选择解析方法' }]}
          >
            <Select>
              <Option value="mineru">MinerU</Option>
              <Option value="dots">DOTS</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 知识库详情模态框 */}
      <Modal
        title={`知识库详情 - ${currentKnowledgeBase?.name || ''}`}
        open={viewModalVisible}
        onCancel={() => {
          // 批量解析可以在后台继续运行
          setViewModalVisible(false);
          // 清除批量解析选择状态
          setBatchParseSelectionMode(false);
          setSelectedDocumentKeys([]);
          // 只有在批量解析完成时才清空 currentKnowledgeBase
          if (!batchParsingStatus.isActive) {
            setCurrentKnowledgeBase(null);
          }
        }}
        width={1000}
        footer={[
          <Button
            key="close"
            onClick={() => {
              // 批量解析可以在后台继续运行
              setViewModalVisible(false);
              // 清除批量解析选择状态
              setBatchParseSelectionMode(false);
              setSelectedDocumentKeys([]);
              // 只有在批量解析完成时才清空 currentKnowledgeBase
              if (!batchParsingStatus.isActive) {
                setCurrentKnowledgeBase(null);
              }
            }}
          >
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
              <Descriptions.Item label="可见范围">
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
                {!batchParseSelectionMode ? (
                  <Button
                    type="default"
                    icon={<ThunderboltOutlined />}
                    loading={batchParsingStatus.isActive}
                    onClick={handleBatchParse}
                    disabled={
                      documentList.length === 0 || batchParsingStatus.isActive
                    }
                  >
                    {batchParsingStatus.isActive
                      ? '正在批量解析...'
                      : '批量解析'}
                  </Button>
                ) : (
                  <>
                    <Button
                      type="primary"
                      icon={<ThunderboltOutlined />}
                      onClick={handleBatchParse}
                      disabled={selectedDocumentKeys.length === 0}
                    >
                      开始解析 ({selectedDocumentKeys.length})
                    </Button>
                    <Button onClick={handleCancelBatchParse}>取消选择</Button>
                  </>
                )}
              </Space>

              {/* 文档搜索区域 */}
              <Space>
                <Input
                  placeholder="搜索文档名称"
                  value={docSearchValue}
                  onChange={(e) => setDocSearchValue(e.target.value)}
                  onPressEnter={handleDocSearch}
                  style={{ width: 200 }}
                  allowClear
                />
                <Button
                  type="primary"
                  icon={<SearchOutlined />}
                  onClick={handleDocSearch}
                  loading={documentLoading}
                  size="small"
                >
                  搜索
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleDocReset}
                  size="small"
                >
                  重置
                </Button>
              </Space>
            </div>

            {(batchParsingStatus.isActive || batchParsingStatus.error) && (
              <Alert
                message={batchParsingStatus.message}
                description={
                  batchParsingStatus.totalDocuments > 0 && (
                    <div>
                      <div
                        style={{
                          fontSize: '12px',
                          color: '#606266',
                          marginBottom: '8px',
                        }}
                      >
                        处理进度: {batchParsingStatus.completedDocuments} /{' '}
                        {batchParsingStatus.totalDocuments}
                      </div>
                      {batchParsingStatus.currentDocumentName && (
                        <div style={{ fontSize: '12px', color: '#1890ff' }}>
                          当前处理: {batchParsingStatus.currentDocumentName}
                        </div>
                      )}
                      {batchParsingStatus.startTime && (
                        <div
                          style={{
                            fontSize: '12px',
                            color: '#999',
                            marginTop: '4px',
                          }}
                        >
                          开始时间:{' '}
                          {new Date(
                            batchParsingStatus.startTime,
                          ).toLocaleString()}
                        </div>
                      )}
                    </div>
                  )
                }
                type={batchParsingStatus.error ? 'error' : 'info'}
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
                rowSelection={
                  batchParseSelectionMode
                    ? {
                        selectedRowKeys: selectedDocumentKeys,
                        onChange: (selectedRowKeys: React.Key[]) =>
                          setSelectedDocumentKeys(selectedRowKeys as string[]),
                        onSelectAll: (selected, selectedRows, changeRows) => {
                          if (selected) {
                            // 全选
                            const allIds = documentList.map((doc) => doc.id);
                            setSelectedDocumentKeys(allIds);
                          } else {
                            // 取消全选
                            setSelectedDocumentKeys([]);
                          }
                        },
                      }
                    : undefined
                }
                rowClassName={(record) => {
                  // 为正在批量解析的文档添加特殊样式
                  const isCurrentBatchDocument =
                    batchParsingStatus.isActive &&
                    batchParsingStatus.currentDocumentName &&
                    record.name === batchParsingStatus.currentDocumentName;

                  return isCurrentBatchDocument ? 'batch-parsing-row' : '';
                }}
                locale={{
                  emptyText: <Empty description="暂无文档数据" />,
                }}
              />

              {/* 文档列表分页 */}
              <div className={styles.documentPaginationWrapper}>
                <Pagination
                  current={docPagination.current}
                  pageSize={docPagination.pageSize}
                  total={docPagination.total}
                  onChange={(page, pageSize) => {
                    setDocPagination((prev) => ({
                      ...prev,
                      current: page,
                      pageSize: pageSize || prev.pageSize,
                    }));
                  }}
                  showSizeChanger
                  showQuickJumper
                  showTotal={(total, range) =>
                    `第 ${range[0]}-${range[1]} 条/共 ${total} 条文档`
                  }
                  pageSizeOptions={['10', '20', '50', '100']}
                  size="small"
                />
              </div>
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
              render: (size: number) =>
                size < 1024
                  ? `${size} B`
                  : size < 1024 * 1024
                    ? `${(size / 1024).toFixed(2)} KB`
                    : `${(size / 1024 / 1024).toFixed(2)} MB`,
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

      {/* 旧的分块规则弹窗已移除，现在使用 ParseConfigModal */}

      {/* 解析进度弹窗 */}
      {/* 解析进度弹窗相关代码已移除 */}

      {/* 角色管理模态框 */}
      <PermissionModal
        visible={permissionModalVisible}
        onCancel={() => setPermissionModalVisible(false)}
        knowledgeBaseId={currentKnowledgeBase?.id || ''}
        knowledgeBaseName={currentKnowledgeBase?.name || ''}
      />

      {/* 解析配置对话框 */}
      <ParseConfigModal
        visible={parseConfigModalVisible}
        documentName={currentParseDoc?.name}
        defaultValues={{
          parser_id: currentParseDoc?.parser_id,
          layout_recognize: currentParseDoc?.parser_config?.layout_recognize,
          chunk_token_num: currentParseDoc?.parser_config?.chunk_token_num,
        }}
        onOk={handleParseConfigOk}
        onCancel={() => setParseConfigModalVisible(false)}
      />
    </div>
  );
};

export default KnowledgeManagementPage;
