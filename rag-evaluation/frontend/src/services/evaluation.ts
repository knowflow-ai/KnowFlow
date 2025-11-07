import { request, uploadFile } from './api';
import axios from 'axios';

// RAGFlow API 配置
const RAGFLOW_API_BASE = import.meta.env.VITE_RAGFLOW_API_URL || 'http://localhost:9380/api/v1';
const RAGFLOW_API_KEY = import.meta.env.VITE_RAGFLOW_API_KEY || '';

const ragflowHeaders: Record<string, string> = {
  'Content-Type': 'application/json'
};

// 只有配置了 API Key 才添加 Authorization header
if (RAGFLOW_API_KEY) {
  ragflowHeaders['Authorization'] = `Bearer ${RAGFLOW_API_KEY}`;
}

const ragflowClient = axios.create({
  baseURL: RAGFLOW_API_BASE,
  timeout: 30000,
  headers: ragflowHeaders
});

// 类型定义
export interface Dataset {
  id: string;
  name: string;
  description?: string;
  file_name: string;
  file_type: string;
  num_samples: number;
  has_reference: boolean;
  has_contexts: boolean;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  error_message?: string;
  created_at: string;
  created_by: string;
}

export interface DatasetUploadParams {
  name: string;
  description?: string;
}

export interface EvaluationTask {
  id: string;
  name?: string;
  kb_id: string;
  dataset_id: string;
  metrics: string[];
  llm_model?: string;
  batch_size?: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  total_samples: number;
  processed_samples: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface TaskCreateParams {
  name?: string;
  chat_id: string;  // 使用 Chat 助手 ID 而不是知识库 ID
  dataset_id: string;
  metrics: string[];
  llm_model?: string;
  batch_size?: number;
}

export interface EvaluationReport {
  task_id: string;
  kb_name: string;
  dataset_name: string;
  overall_score: number;
  metric_scores: {
    [key: string]: {
      mean: number;
      std: number;
      min: number;
      max: number;
    };
  };
  summary: string;
  recommendations: string[];
  createdAt: string;
  successRate?: number;
  totalSamples?: number;
  lowScoreSamples?: Array<{
    question: string;
    score: number;
    issue: string;
  }>;
  detailed_scores?: Array<{
    user_input: string;
    actual_answer: string;
    expected_answer: string;
    contexts: string[];
    [key: string]: any;  // for metric scores
  }>;
}

export interface Metric {
  name: string;
  display_name: string;
  description: string;
  type: 'llm_based' | 'traditional' | 'custom';
  requires_reference: boolean;
  requires_contexts: boolean;
  default_enabled: boolean;
}

export interface QuickEvaluateParams {
  question: string;
  answer: string;
  contexts?: string[];
  metric?: string;
}

// 数据集相关 API
export const datasetApi = {
  // 上传数据集
  upload: (file: File, params: DatasetUploadParams) => {
    return uploadFile('/evaluation/datasets', file, params);
  },

  // 获取数据集列表
  list: (params?: { offset?: number; limit?: number }) => {
    return request.get<{
      datasets: Dataset[];
      total: number;
      offset: number;
      limit: number;
    }>('/evaluation/datasets', { params });
  },

  // 获取数据集详情
  get: (datasetId: string) => {
    return request.get<Dataset>(`/evaluation/datasets/${datasetId}`);
  },

  // 获取数据集样本
  getSamples: (datasetId: string, params?: { offset?: number; limit?: number }) => {
    return request.get<{
      samples: any[];
      offset: number;
      limit: number;
    }>(`/evaluation/datasets/${datasetId}/samples`, { params });
  },

  // 删除数据集
  delete: (datasetId: string) => {
    return request.delete(`/evaluation/datasets/${datasetId}`);
  },

  // 批量删除数据集
  batchDelete: (datasetIds: string[]) => {
    return request.delete<{
      message: string;
      deleted_count: number;
      total_count: number;
      failed_count: number;
      failed_ids?: string[];
    }>('/evaluation/datasets/batch', { dataset_ids: datasetIds });
  },

  // 生成示例数据集
  generateSample: (type: 'basic' | 'with_reference' | 'with_contexts') => {
    return request.post<Dataset>(`/evaluation/datasets/generate/${type}`);
  },
  
  // AI生成数据集
  generateAIDataset: (params: {
    kb_id: string;
    sample_count: number;
    question_types: string[];
  }) => {
    return request.post<Dataset>('/evaluation/datasets/generate/ai', params);
  },
};

// 评测任务相关 API
export const taskApi = {
  // 创建评测任务
  create: (params: TaskCreateParams) => {
    return request.post<EvaluationTask>('/evaluation/tasks', params);
  },

  // 获取任务列表
  list: (params?: { status?: string; offset?: number; limit?: number }) => {
    return request.get<{
      tasks: EvaluationTask[];
      total: number;
      offset: number;
      limit: number;
    }>('/evaluation/tasks', { params });
  },

  // 获取任务状态
  getStatus: (taskId: string) => {
    return request.get<EvaluationTask>(`/evaluation/tasks/${taskId}`);
  },

  // 开始任务
  start: (taskId: string) => {
    return request.post(`/evaluation/tasks/${taskId}/start`);
  },

  // 暂停任务
  pause: (taskId: string) => {
    return request.post(`/evaluation/tasks/${taskId}/pause`);
  },

  // 取消任务
  cancel: (taskId: string) => {
    return request.post(`/evaluation/tasks/${taskId}/cancel`);
  },

  // 重试任务
  retry: (taskId: string) => {
    return request.post(`/evaluation/tasks/${taskId}/retry`);
  },

  // 删除任务
  delete: (taskId: string) => {
    return request.delete(`/evaluation/tasks/${taskId}`);
  },

  // 批量删除任务
  batchDelete: (taskIds: string[]) => {
    return request.delete<{
      message: string;
      deleted_count: number;
      total_count: number;
      failed_count: number;
      running_count: number;
      failed_ids?: string[];
      running_tasks?: string[];
    }>('/evaluation/tasks/batch', { task_ids: taskIds });
  },
};

// 报告相关 API
export const reportApi = {
  // 获取评测报告
  get: (taskId: string) => {
    return request.get<EvaluationReport>(`/evaluation/reports/${taskId}`);
  },

  // 导出报告
  export: (taskId: string, format: 'pdf' | 'excel' | 'json') => {
    return request.get(`/evaluation/reports/${taskId}/export`, {
      params: { format },
      responseType: 'blob',
    });
  },

  // 获取报告列表
  list: (params?: { kb_id?: string; start_date?: string; end_date?: string }) => {
    return request.get<EvaluationReport[]>('/evaluation/reports', { params });
  },

  // 删除报告
  delete: (taskId: string) => {
    return request.delete(`/evaluation/reports/${taskId}`);
  },

  // 批量删除报告
  batchDelete: (taskIds: string[]) => {
    return request.delete<{
      message: string;
      deleted_count: number;
      total_count: number;
      failed_count: number;
    }>('/evaluation/reports/batch', { task_ids: taskIds });
  },

  // 对比报告
  compare: (taskIds: string[]) => {
    return request.post('/evaluation/reports/compare', { task_ids: taskIds });
  },
};

// 指标相关 API
export const metricApi = {
  // 获取可用指标列表
  list: (type?: 'llm_based' | 'traditional' | 'custom') => {
    return request.get<{ metrics: Metric[] }>('/evaluation/metrics', {
      params: type ? { type } : undefined,
    });
  },

  // 获取指标分组
  getGroups: () => {
    return request.get<{
      groups: {
        [key: string]: Metric[];
      };
    }>('/evaluation/metrics/groups');
  },

  // 验证指标配置
  validate: (metrics: string[], hasReference: boolean, hasContexts: boolean) => {
    return request.post('/evaluation/metrics/validate', {
      metrics,
      has_reference: hasReference,
      has_contexts: hasContexts,
    });
  },
};

// 快速评测 API
export const quickEvaluateApi = {
  // 快速评测单个问答对
  evaluate: (params: QuickEvaluateParams) => {
    return request.post<{ score: number; metric: string }>('/evaluation/quick', params);
  },

  // 批量快速评测
  batchEvaluate: (samples: QuickEvaluateParams[]) => {
    return request.post<{ results: Array<{ score: number; metric: string }> }>(
      '/evaluation/quick/batch',
      { samples }
    );
  },
};

// 系统相关 API
export const systemApi = {
  // 健康检查
  health: () => {
    return request.get<{
      status: string;
      service: string;
      timestamp: string;
      metrics_available: number;
    }>('/evaluation/health');
  },

  // 获取系统统计
  getStatistics: () => {
    return request.get('/evaluation/statistics');
  },

  // 获取配置
  getConfig: () => {
    return request.get('/evaluation/config');
  },

  // 更新配置
  updateConfig: (config: any) => {
    return request.put('/evaluation/config', config);
  },

  // 测试API连接
  testConnection: (config: {
    provider: string;
    apiKey: string;
    endpoint?: string;
    model: string;
  }) => {
    return request.post<{
      success: boolean;
      message: string;
      details?: any;
    }>('/evaluation/test-connection', config);
  },
};

// 已废弃：使用 chatApi 替代知识库相关功能
// export const knowledgeBaseApi = { ... };

// Chat 助手相关 API（直接调用 RAGFlow）
export const chatApi = {
  // 获取 Chat 助手列表
  list: async (params?: { page?: number; page_size?: number; name?: string }) => {
    const response = await ragflowClient.get('/chats', { params });
    return response.data;
  },

  // 获取 Chat 助手详情
  get: async (chatId: string) => {
    const response = await ragflowClient.get(`/chats/${chatId}`);
    return response.data;
  },
};