/**
 * 统一的前端服务管理
 * 整合所有API调用，避免重复代码
 */
// @ts-nocheck

import { request, uploadFile } from './api';
import axios from 'axios';
import {
  ResponseHandler,
  ValidationHelper,
  FormatHelper,
  StatusHelper,
  NotificationHelper,
  BatchHelper
} from '../utils/shared';

// ==================== 类型定义 ====================

export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data?: T;
  error?: string;
  details?: any;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface BatchDeleteResult {
  message: string;
  deleted_count: number;
  total_count: number;
  failed_count: number;
  failed_ids?: string[];
  running_count?: number;
  running_tasks?: string[];
}

// ==================== 基础服务类 ====================

abstract class BaseService {
  protected baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  protected async get<T = any>(url: string, params?: any): Promise<T> {
    try {
      const response = await request.get<T>(`${this.baseUrl}${url}`, { params });
      return this.handleResponse(response);
    } catch (error) {
      this.handleError(error, 'GET', url);
      throw error;
    }
  }

  protected async post<T = any>(url: string, data?: any): Promise<T> {
    try {
      const response = await request.post<T>(`${this.baseUrl}${url}`, data);
      return this.handleResponse(response);
    } catch (error) {
      this.handleError(error, 'POST', url);
      throw error;
    }
  }

  protected async put<T = any>(url: string, data?: any): Promise<T> {
    try {
      const response = await request.put<T>(`${this.baseUrl}${url}`, data);
      return this.handleResponse(response);
    } catch (error) {
      this.handleError(error, 'PUT', url);
      throw error;
    }
  }

  protected async delete<T = any>(url: string, data?: any): Promise<T> {
    try {
      const response = await request.delete<T>(`${this.baseUrl}${url}`, data);
      return this.handleResponse(response);
    } catch (error) {
      this.handleError(error, 'DELETE', url);
      throw error;
    }
  }

  protected async upload<T = any>(url: string, file: File, additionalData?: Record<string, any>): Promise<T> {
    try {
      const response = await uploadFile(`${this.baseUrl}${url}`, file, additionalData);
      return this.handleResponse(response);
    } catch (error) {
      this.handleError(error, 'UPLOAD', url);
      throw error;
    }
  }

  private handleResponse<T>(response: any): T {
    if (ResponseHandler.isSuccess(response)) {
      return response.data ?? response;
    }
    throw new Error(ResponseHandler.getErrorMessage(response));
  }

  private handleError(error: any, method: string, url: string): void {
    const errorMessage = ResponseHandler.formatError(error);
    console.error(`[API Error] ${method} ${url}: ${errorMessage}`);
    NotificationHelper.error(errorMessage, '请求失败');
  }
}

// ==================== 配置服务 ====================

export class ConfigService extends BaseService {
  constructor() {
    super('/evaluation');
  }

  // 获取系统配置
  async getConfig(): Promise<{ api: any }> {
    const response = await this.get<ApiResponse>('/config');
    return response.data || {};
  }

  // 更新系统配置
  async updateConfig(config: any): Promise<void> {
    // 验证配置
    const errors = ValidationHelper.validateApiConfig(config);
    if (errors.length > 0) {
      throw new Error(errors.join('; '));
    }

    await this.put('/config', { api_config: config });
    NotificationHelper.success('配置更新成功');
  }

  // 测试API连接
  async testConnection(config: {
    provider: string;
    apiKey: string;
    endpoint?: string;
    model: string;
  }): Promise<{ success: boolean; message: string; details?: any }> {
    // 验证配置
    const errors = ValidationHelper.validateApiConfig(config);
    if (errors.length > 0) {
      throw new Error(errors.join('; '));
    }

    try {
      const response = await this.post<ApiResponse<{ success: boolean; message: string; details?: any }>>('/test-connection', config);
      return response.data || { success: false, message: '测试失败' };
    } catch (error) {
      throw new Error('连接测试失败，请检查配置信息');
    }
  }
}

// ==================== 数据集服务 ====================

export class DatasetService extends BaseService {
  constructor() {
    super('/evaluation/datasets');
  }

  // 获取数据集列表
  async list(params?: { offset?: number; limit?: number }): Promise<PaginatedResponse<any>> {
    // 参数验证
    if (params?.offset !== undefined && params.offset < 0) {
      throw new Error('offset不能小于0');
    }
    if (params?.limit !== undefined && (params.limit < 1 || params.limit > 100)) {
      throw new Error('limit必须在1-100之间');
    }

    const response = await this.get<ApiResponse<PaginatedResponse<any>>>('', params);
    return response.data || { items: [], total: 0, offset: 0, limit: 10 };
  }

  // 获取数据集详情
  async get(id: string): Promise<any> {
    // 验证ID
    if (!id?.trim()) {
      throw new Error('数据集ID不能为空');
    }

    const response = await this.get<ApiResponse>(`/${id}`);
    if (!response.data) {
      throw new Error('数据集不存在');
    }
    return response.data;
  }

  // 创建数据集
  async create(file: File, params: { name: string; description?: string }): Promise<{ dataset_id: string }> {
    // 验证参数
    if (!file) {
      throw new Error('请选择要上传的文件');
    }

    // 验证文件类型
    const allowedTypes = ['.json', '.csv', '.xlsx', '.xls'];
    const fileError = ValidationHelper.validateFile(file, allowedTypes, 50); // 50MB限制
    if (fileError) {
      throw new Error(fileError);
    }

    // 验证名称
    if (!params.name?.trim()) {
      throw new Error('数据集名称不能为空');
    }

    try {
      const response = await this.upload<ApiResponse<{ dataset_id: string }>>('', file, params);
      NotificationHelper.success('数据集创建成功');
      return response.data || { dataset_id: '' };
    } catch (error) {
      throw new Error('数据集创建失败，请检查文件格式和内容');
    }
  }

  // 删除数据集
  async delete(id: string): Promise<void> {
    if (!id?.trim()) {
      throw new Error('数据集ID不能为空');
    }

    try {
      await this.delete(`/${id}`);
      NotificationHelper.success('数据集删除成功');
    } catch (error) {
      throw new Error('数据集删除失败，可能不存在或正在被使用');
    }
  }

  // 批量删除数据集
  async batchDelete(ids: string[]): Promise<BatchDeleteResult> {
    if (!Array.isArray(ids) || ids.length === 0) {
      throw new Error('请选择要删除的数据集');
    }

    if (ids.some(id => !id?.trim())) {
      throw new Error('数据集ID不能为空');
    }

    try {
      const response = await this.delete<ApiResponse<BatchDeleteResult>>('/batch', { dataset_ids: ids });
      return response.data || {
        message: '删除完成',
        deleted_count: 0,
        total_count: ids.length,
        failed_count: ids.length
      };
    } catch (error) {
      console.error('Batch delete failed:', error);
      return {
        message: '删除失败',
        deleted_count: 0,
        total_count: ids.length,
        failed_count: ids.length
      };
    }
  }

  // 获取数据集样本
  async getSamples(id: string, params?: { offset?: number; limit?: number }): Promise<{ samples: any[] }> {
    const response = await this.get<ApiResponse<{ samples: any[] }>>(`/${id}/samples`, params);
    return response.data || { samples: [] };
  }

  // 生成示例数据集
  async generateSample(type: 'basic' | 'with_reference' | 'with_contexts'): Promise<any> {
    const response = await this.post<ApiResponse>(`/generate/${type}`);
    return response.data;
  }
}

// ==================== 任务服务 ====================

export class TaskService extends BaseService {
  constructor() {
    super('/evaluation/tasks');
  }

  // 获取任务列表
  async list(params?: { offset?: number; limit?: number; status?: string }): Promise<PaginatedResponse<any>> {
    const response = await this.get<ApiResponse<PaginatedResponse<any>>>('', params);
    return response.data || { items: [], total: 0, offset: 0, limit: 10 };
  }

  // 获取任务详情
  async get(id: string): Promise<any> {
    const response = await this.get<ApiResponse>(`/${id}`);
    return response.data;
  }

  // 创建任务
  async create(data: {
    name?: string;
    chat_id: string;
    dataset_id: string;
    metrics: string[];
    llm_model?: string;
    batch_size?: number;
  }): Promise<{ task_id: string }> {
    const response = await this.post<ApiResponse<{ task_id: string }>>('', data);
    return response.data || { task_id: '' };
  }

  // 启动任务
  async start(id: string): Promise<void> {
    await this.post(`/${id}/start`);
  }

  // 暂停任务
  async pause(id: string): Promise<void> {
    await this.post(`/${id}/pause`);
  }

  // 取消任务
  async cancel(id: string): Promise<void> {
    await this.post(`/${id}/cancel`);
  }

  // 删除任务
  async delete(id: string): Promise<void> {
    await this.delete(`/${id}`);
  }

  // 批量删除任务
  async batchDelete(ids: string[]): Promise<BatchDeleteResult> {
    const response = await this.delete<ApiResponse<BatchDeleteResult>>('/batch', { task_ids: ids });
    return response.data || {
      message: '删除失败',
      deleted_count: 0,
      total_count: ids.length,
      failed_count: ids.length
    };
  }
}

// ==================== 报告服务 ====================

export class ReportService extends BaseService {
  constructor() {
    super('/evaluation/reports');
  }

  // 获取报告列表
  async list(params?: {
    kb_id?: string;
    start_date?: string;
    end_date?: string;
    offset?: number;
    limit?: number;
  }): Promise<{ reports: any[]; total: number }> {
    const response = await this.get<ApiResponse<{ reports: any[]; total: number }>>('', params);
    return response.data || { reports: [], total: 0 };
  }

  // 获取报告详情
  async get(id: string): Promise<any> {
    const response = await this.get<ApiResponse>(`/${id}`);
    return response.data;
  }

  // 导出报告
  async export(id: string, format: 'pdf' | 'excel' | 'json'): Promise<Blob> {
    const response = await request.get(`/${id}/export`, {
      params: { format },
      responseType: 'blob'
    });
    return response;
  }

  // 删除报告
  async delete(id: string): Promise<void> {
    await this.delete(`/${id}`);
  }

  // 批量删除报告
  async batchDelete(ids: string[]): Promise<BatchDeleteResult> {
    const response = await this.delete<ApiResponse<BatchDeleteResult>>('/batch', { task_ids: ids });
    return response.data || {
      message: '删除失败',
      deleted_count: 0,
      total_count: ids.length,
      failed_count: ids.length
    };
  }

  // 对比报告
  async compare(ids: string[]): Promise<any> {
    const response = await this.post<ApiResponse>('/compare', { task_ids: ids });
    return response.data;
  }
}

// ==================== 指标服务 ====================

export class MetricService extends BaseService {
  constructor() {
    super('/evaluation/metrics');
  }

  // 获取指标列表
  async list(type?: 'llm_based' | 'traditional' | 'custom'): Promise<{ metrics: any[] }> {
    const response = await this.get<ApiResponse<{ metrics: any[] }>>('', { type });
    return response.data || { metrics: [] };
  }

  // 获取指标分组
  async getGroups(): Promise<{ groups: Record<string, any[]> }> {
    const response = await this.get<ApiResponse<{ groups: Record<string, any[]> }>>('/groups');
    return response.data || { groups: {} };
  }

  // 验证指标配置
  async validate(data: {
    metrics: string[];
    has_reference: boolean;
    has_contexts: boolean;
  }): Promise<{ valid: boolean }> {
    const response = await this.post<ApiResponse<{ valid: boolean }>>('/validate', data);
    return response.data || { valid: false };
  }
}

// ==================== 快速评测服务 ====================

export class QuickEvaluateService extends BaseService {
  constructor() {
    super('/evaluation/quick');
  }

  // 快速评测单个问答对
  async evaluate(data: {
    question: string;
    answer: string;
    contexts?: string[];
    metric?: string;
  }): Promise<{ score: number; metric: string }> {
    const response = await this.post<ApiResponse<{ score: number; metric: string }>>('', data);
    return response.data || { score: 0, metric: '' };
  }

  // 批量快速评测
  async batchEvaluate(samples: Array<{
    question: string;
    answer: string;
    contexts?: string[];
    metric?: string;
  }>): Promise<{ results: Array<{ score: number; metric: string }> }> {
    const response = await this.post<ApiResponse<{ results: Array<{ score: number; metric: string }> }>>('/batch', { samples });
    return response.data || { results: [] };
  }
}

// ==================== RAGFlow Chat 服务 ====================

export class ChatService {
  private client: any;
  private headers: Record<string, string>;

  constructor() {
    const baseUrl = import.meta.env.VITE_RAGFLOW_API_URL || 'http://localhost:9380/api/v1';
    const apiKey = import.meta.env.VITE_RAGFLOW_API_KEY || '';

    this.headers = {
      'Content-Type': 'application/json'
    };

    if (apiKey) {
      this.headers['Authorization'] = `Bearer ${apiKey}`;
    }

    this.client = axios.create({
      baseURL: baseUrl,
      timeout: 30000,
      headers: this.headers
    });
  }

  // 获取Chat助手列表
  async list(params?: { page?: number; page_size?: number; name?: string }): Promise<any> {
    const response = await this.client.get('/chats', { params });
    return response.data;
  }

  // 获取Chat助手详情
  async get(id: string): Promise<any> {
    const response = await this.client.get(`/chats/${id}`);
    return response.data;
  }
}

// ==================== 统一服务管理器 ====================

export class ServiceManager {
  private static instance: ServiceManager;

  private _config: ConfigService;
  private _dataset: DatasetService;
  private _task: TaskService;
  private _report: ReportService;
  private _metric: MetricService;
  private _quickEvaluate: QuickEvaluateService;
  private _chat: ChatService;

  private constructor() {
    this._config = new ConfigService();
    this._dataset = new DatasetService();
    this._task = new TaskService();
    this._report = new ReportService();
    this._metric = new MetricService();
    this._quickEvaluate = new QuickEvaluateService();
    this._chat = new ChatService();
  }

  static getInstance(): ServiceManager {
    if (!ServiceManager.instance) {
      ServiceManager.instance = new ServiceManager();
    }
    return ServiceManager.instance;
  }

  get config(): ConfigService {
    return this._config;
  }

  get dataset(): DatasetService {
    return this._dataset;
  }

  get task(): TaskService {
    return this._task;
  }

  get report(): ReportService {
    return this._report;
  }

  get metric(): MetricService {
    return this._metric;
  }

  get quickEvaluate(): QuickEvaluateService {
    return this._quickEvaluate;
  }

  get chat(): ChatService {
    return this._chat;
  }
}

// 导出单例实例
const serviceManager = ServiceManager.getInstance();

// 导出便捷的服务实例
export const configService = serviceManager.config;
export const datasetService = serviceManager.dataset;
export const taskService = serviceManager.task;
export const reportService = serviceManager.report;
export const metricService = serviceManager.metric;
export const quickEvaluateService = serviceManager.quickEvaluate;
export const chatService = serviceManager.chat;

// 同时导出 serviceManager 实例
export { serviceManager };