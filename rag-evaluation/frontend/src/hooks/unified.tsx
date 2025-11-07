/**
 * 统一的Hook管理
 * 整合所有自定义Hook，避免重复代码
 */
// @ts-nocheck

import { useState, useEffect, useCallback, useRef } from 'react';
import { message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { serviceManager } from '../services/unified';

// ==================== 通用Hook ====================

interface UseApiOptions<T> {
  immediate?: boolean;
  onSuccess?: (data: T) => void;
  onError?: (error: any) => void;
}

export function useApi<T = any>(
  apiCall: () => Promise<T>,
  options: UseApiOptions<T> = {}
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiCall();
      setData(result);
      options.onSuccess?.(result);
    } catch (err) {
      setError(err);
      options.onError?.(err);
    } finally {
      setLoading(false);
    }
  }, [apiCall]);

  useEffect(() => {
    if (options.immediate) {
      execute();
    }
  }, [execute, options.immediate]);

  return { data, loading, error, execute };
}

// ==================== 分页Hook ====================

interface UsePaginationOptions {
  defaultPageSize?: number;
  defaultOffset?: number;
}

export function usePagination(options: UsePaginationOptions = {}) {
  const { defaultPageSize = 10, defaultOffset = 0 } = options;

  const [offset, setOffset] = useState(defaultOffset);
  const [limit, setLimit] = useState(defaultPageSize);
  const [total, setTotal] = useState(0);

  const reset = useCallback(() => {
    setOffset(defaultOffset);
  }, [defaultOffset]);

  const nextPage = useCallback(() => {
    if (offset + limit < total) {
      setOffset(offset + limit);
    }
  }, [offset, limit, total]);

  const prevPage = useCallback(() => {
    if (offset - limit >= 0) {
      setOffset(offset - limit);
    }
  }, [offset, limit]);

  return {
    offset,
    limit,
    total,
    setOffset,
    setLimit,
    setTotal,
    reset,
    nextPage,
    prevPage,
    hasNext: offset + limit < total,
    hasPrev: offset > 0
  };
}

// ==================== 批量操作Hook ====================

interface BatchDeleteOptions {
  apiCall: (ids: string[]) => Promise<{
    message: string;
    deleted_count: number;
    total_count: number;
    failed_count: number;
    failed_ids?: string[];
    running_count?: number;
    running_tasks?: string[];
  }>;
  itemName: string;
  onSuccess?: () => void;
  skipRunning?: boolean;
}

export function useBatchDelete({
  apiCall,
  itemName,
  onSuccess,
  skipRunning = false
}: BatchDeleteOptions) {
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const appContext = App.useApp();

  const onSelectChange = useCallback((newSelectedRowKeys: React.Key[]) => {
    setSelectedRowKeys(newSelectedRowKeys);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedRowKeys([]);
  }, []);

  const handleBatchDelete = useCallback(async () => {
    if (selectedRowKeys.length === 0) {
      message.warning(`请选择要删除的${itemName}`);
      return;
    }

    if (appContext.modal) {
      appContext.modal.confirm({
        title: '确认删除',
        content: (
          <div>
            <p>确定要删除选中的 <strong>{selectedRowKeys.length} 个{itemName}</strong> 吗？</p>
            <p style={{ color: '#ff4d4f', fontSize: '12px' }}>此操作无法撤销。</p>
          </div>
        ),
        okText: '删除',
        okType: 'danger',
        cancelText: '取消',
        width: 400,
        onOk: async () => {
          setBatchDeleting(true);
          try {
            const response = await apiCall(selectedRowKeys as string[]);

            if (response.deleted_count > 0) {
              message.success(response.message || `成功删除 ${response.deleted_count} 个${itemName}`);
              clearSelection();
              onSuccess?.();
            }

            if (response.failed_count > 0) {
              message.warning(`${response.failed_count} 个${itemName}删除失败`);
            }

            if (response.running_count && response.running_count > 0) {
              message.info(`${response.running_count} 个运行中的${itemName}已跳过`);
            }
          } catch (error) {
            console.error('Batch delete failed:', error);
            message.error('批量删除失败');
          } finally {
            setBatchDeleting(false);
          }
        }
      });
    }
  }, [selectedRowKeys, apiCall, itemName, skipRunning, clearSelection, onSuccess, appContext]);

  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
    getCheckboxProps: skipRunning
      ? (record: any) => ({
          disabled: record.status === 'running',
          name: record.name,
        })
      : undefined,
  };

  return {
    selectedRowKeys,
    setSelectedRowKeys,
    batchDeleting,
    clearSelection,
    handleBatchDelete,
    rowSelection,
  };
}

// ==================== 数据集Hook ====================

export function useDatasets() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const pagination = usePagination();

  const fetchDatasets = useCallback(async () => {
    setLoading(true);
    try {
      const result = await serviceManager.dataset.list({
        offset: pagination.offset,
        limit: pagination.limit
      });
      setDatasets(result.items);
      setTotal(result.total);
      pagination.setTotal(result.total);
    } catch (error) {
      console.error('Failed to fetch datasets:', error);
      message.error('获取数据集列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination]);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  const createDataset = useCallback(async (file: File, params: { name: string; description?: string }) => {
    try {
      const result = await serviceManager.dataset.create(file, params);
      message.success('数据集创建成功');
      fetchDatasets();
      return result.dataset_id;
    } catch (error) {
      console.error('Failed to create dataset:', error);
      message.error('创建数据集失败');
      throw error;
    }
  }, [fetchDatasets]);

  const deleteDataset = useCallback(async (id: string) => {
    try {
      await serviceManager.dataset.deleteDataset(id);
      message.success('数据集删除成功');
      fetchDatasets();
    } catch (error) {
      console.error('Failed to delete dataset:', error);
      message.error('删除数据集失败');
      throw error;
    }
  }, [fetchDatasets]);

  const batchDelete = useBatchDelete({
    apiCall: serviceManager.dataset.batchDelete,
    itemName: '数据集',
    onSuccess: fetchDatasets
  });

  return {
    datasets,
    loading,
    total,
    pagination,
    fetchDatasets,
    createDataset,
    deleteDataset,
    ...batchDelete
  };
}

// ==================== 任务Hook ====================

export function useTasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const intervalRef = useRef<number | null>(null);
  const navigate = useNavigate();
  const pagination = usePagination();

  const fetchTasks = useCallback(async (status?: string) => {
    setLoading(true);
    try {
      const result = await serviceManager.task.list({
        offset: pagination.offset,
        limit: pagination.limit,
        status
      });
      setTasks(result.items);
      setTotal(result.total);
      pagination.setTotal(result.total);
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
      message.error('获取任务列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // 自动刷新逻辑
  useEffect(() => {
    const hasRunningTasks = tasks.some(task => task.status === 'running');

    if (hasRunningTasks && !intervalRef.current) {
      intervalRef.current = setInterval(() => {
        fetchTasks();
      }, 3000);
    } else if (!hasRunningTasks && intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [tasks, fetchTasks]);

  const createTask = useCallback(async (data: any) => {
    try {
      const result = await serviceManager.task.create(data);
      message.success('任务创建成功');
      fetchTasks();
      return result.task_id;
    } catch (error) {
      console.error('Failed to create task:', error);
      message.error('创建任务失败');
      throw error;
    }
  }, [fetchTasks]);

  const deleteTask = useCallback(async (id: string) => {
    try {
      await serviceManager.task.deleteTask(id);
      message.success('任务删除成功');
      fetchTasks();
    } catch (error) {
      console.error('Failed to delete task:', error);
      message.error('删除任务失败');
      throw error;
    }
  }, [fetchTasks]);

  const handleTaskClick = useCallback((record: any) => {
    if (record.status === 'completed') {
      navigate(`/reports?task_id=${record.id}`);
    } else {
      navigate(`/tasks?task_id=${record.id}`);
    }
  }, [navigate]);

  const batchDelete = useBatchDelete({
    apiCall: serviceManager.task.batchDelete,
    itemName: '任务',
    onSuccess: fetchTasks,
    skipRunning: true
  });

  return {
    tasks,
    loading,
    total,
    pagination,
    fetchTasks,
    createTask,
    deleteTask,
    handleTaskClick,
    ...batchDelete
  };
}

// ==================== 报告Hook ====================

export function useReports() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const pagination = usePagination();

  const fetchReports = useCallback(async (filters?: {
    kb_id?: string;
    start_date?: string;
    end_date?: string;
  }) => {
    setLoading(true);
    try {
      const result = await serviceManager.report.list({
        ...filters,
        offset: pagination.offset,
        limit: pagination.limit
      });
      setReports(result.reports);
      setTotal(result.total);
      pagination.setTotal(result.total);
    } catch (error) {
      console.error('Failed to fetch reports:', error);
      message.error('获取报告列表失败');
    } finally {
      setLoading(false);
    }
  }, [pagination]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const deleteReport = useCallback(async (id: string) => {
    try {
      await serviceManager.report.deleteReport(id);
      message.success('报告删除成功');
      fetchReports();
    } catch (error) {
      console.error('Failed to delete report:', error);
      message.error('删除报告失败');
      throw error;
    }
  }, [fetchReports]);

  const exportReport = useCallback(async (id: string, format: 'pdf' | 'excel' | 'json') => {
    try {
      const blob = await serviceManager.report.export(id, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${id}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      message.success('报告导出成功');
    } catch (error) {
      console.error('Failed to export report:', error);
      message.error('导出报告失败');
      throw error;
    }
  }, []);

  const batchDelete = useBatchDelete({
    apiCall: serviceManager.report.batchDelete,
    itemName: '报告',
    onSuccess: fetchReports
  });

  return {
    reports,
    loading,
    total,
    pagination,
    fetchReports,
    deleteReport,
    exportReport,
    ...batchDelete
  };
}

// ==================== 配置Hook ====================

export function useConfig() {
  const [config, setConfig] = useState<any>({});
  const [loading, setLoading] = useState(false);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const result = await serviceManager.config.getConfig();
      setConfig(result);
    } catch (error) {
      console.error('Failed to fetch config:', error);
      message.error('获取配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const updateConfig = useCallback(async (newConfig: any) => {
    try {
      await serviceManager.config.updateConfig(newConfig);
      message.success('配置更新成功');
      fetchConfig();
    } catch (error) {
      console.error('Failed to update config:', error);
      message.error('更新配置失败');
      throw error;
    }
  }, [fetchConfig]);

  const testConnection = useCallback(async (apiConfig: any) => {
    try {
      const result = await serviceManager.config.testConnection(apiConfig);
      if (result.success) {
        message.success(result.message || '连接测试成功');
      } else {
        message.error(result.message || '连接测试失败');
      }
      return result;
    } catch (error) {
      console.error('Failed to test connection:', error);
      message.error('连接测试失败');
      throw error;
    }
  }, []);

  return {
    config,
    loading,
    fetchConfig,
    updateConfig,
    testConnection
  };
}

// ==================== 指标Hook ====================

export function useMetrics() {
  const [metrics, setMetrics] = useState<any[]>([]);
  const [groups, setGroups] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(false);

  const fetchMetrics = useCallback(async (type?: string) => {
    setLoading(true);
    try {
      const result = await serviceManager.metric.list(type as any);
      setMetrics(result.metrics);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
      message.error('获取指标列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchGroups = useCallback(async () => {
    try {
      const result = await serviceManager.metric.getGroups();
      setGroups(result.groups);
    } catch (error) {
      console.error('Failed to fetch metric groups:', error);
      message.error('获取指标分组失败');
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    fetchGroups();
  }, [fetchMetrics, fetchGroups]);

  return {
    metrics,
    groups,
    loading,
    fetchMetrics,
    fetchGroups
  };
}

// ==================== Chat助手Hook ====================

export function useChatAssistants() {
  const [assistants, setAssistants] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchAssistants = useCallback(async () => {
    setLoading(true);
    try {
      const result = await serviceManager.chat.list();
      setAssistants(result.data || []);
    } catch (error) {
      console.error('Failed to fetch chat assistants:', error);
      message.error('获取对话助手列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAssistants();
  }, [fetchAssistants]);

  return {
    assistants,
    loading,
    fetchAssistants
  };
}

// ==================== 仪表盘Hook ====================

export function useDashboard() {
  const [stats] = useState<any>({});
  const [loading, setLoading] = useState(false);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      // 这里可以调用统计API
      // const result = await serviceManager.config.getStatistics();
      // setStats(result);
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
      message.error('获取统计数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return {
    stats,
    loading,
    fetchStats
  };
}