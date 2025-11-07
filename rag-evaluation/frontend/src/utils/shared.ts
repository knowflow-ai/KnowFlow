/**
 * 前端共享工具函数
 * 消除重复代码，提供统一的工具函数
 */

// ==================== 响应处理工具 ====================

export interface ApiError {
  success: false;
  error: string;
  details?: any;
}

export interface ApiSuccess<T = any> {
  success: true;
  message: string;
  data?: T;
}

export type ApiResponse<T = any> = ApiSuccess<T> | ApiError;

export class ResponseHandler {
  static isSuccess<T>(response: ApiResponse<T>): response is ApiSuccess<T> {
    return response.success === true;
  }

  static getErrorMessage(response: ApiResponse): string {
    if (ResponseHandler.isSuccess(response)) {
      return '';
    }
    return response.error || '未知错误';
  }

  static extractData<T>(response: ApiResponse<T>): T | null {
    if (ResponseHandler.isSuccess(response)) {
      return response.data ?? null;
    }
    return null;
  }

  static formatError(error: any): string {
    if (typeof error === 'string') {
      return error;
    }
    if (error?.response?.data?.error) {
      return error.response.data.error;
    }
    if (error?.message) {
      return error.message;
    }
    return '操作失败';
  }
}

// ==================== 验证工具 ====================

export class ValidationHelper {
  static validateRequired(value: any, fieldName: string): string | null {
    if (value === null || value === undefined || value === '') {
      return `${fieldName}不能为空`;
    }
    return null;
  }

  static validateEmail(email: string): string | null {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return '邮箱格式不正确';
    }
    return null;
  }

  static validateUrl(url: string): string | null {
    try {
      new URL(url);
      return null;
    } catch {
      return 'URL格式不正确';
    }
  }

  static validateFile(file: File, allowedTypes: string[], maxSizeMB: number = 10): string | null {
    // 检查文件类型
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedTypes.includes(fileExtension)) {
      return `不支持的文件类型，支持的格式: ${allowedTypes.join(', ')}`;
    }

    // 检查文件大小
    const maxSizeBytes = maxSizeMB * 1024 * 1024;
    if (file.size > maxSizeBytes) {
      return `文件大小不能超过 ${maxSizeMB}MB`;
    }

    return null;
  }

  static validateApiConfig(config: any): string[] {
    const errors: string[] = [];

    if (!config.provider?.trim()) {
      errors.push('提供商不能为空');
    }

    if (!config.apiKey?.trim()) {
      errors.push('API Key不能为空');
    }

    if (!config.model?.trim()) {
      errors.push('模型不能为空');
    }

    const validProviders = ['siliconflow', 'deepseek', 'zhipu', 'openai'];
    if (config.provider && !validProviders.includes(config.provider.toLowerCase())) {
      errors.push(`不支持的提供商: ${config.provider}，支持的提供商: ${validProviders.join(', ')}`);
    }

    return errors;
  }

  static validateTaskConfig(config: any): string[] {
    const errors: string[] = [];

    if (!config.chat_id?.trim()) {
      errors.push('对话ID不能为空');
    }

    if (!config.dataset_id?.trim()) {
      errors.push('数据集ID不能为空');
    }

    if (!Array.isArray(config.metrics) || config.metrics.length === 0) {
      errors.push('评测指标不能为空');
    } else {
      const validMetrics = [
        'faithfulness', 'answer_correctness', 'context_precision',
        'context_recall', 'answer_relevancy'
      ];
      const invalidMetrics = config.metrics.filter((m: string) => !validMetrics.includes(m));
      if (invalidMetrics.length > 0) {
        errors.push(`不支持的评测指标: ${invalidMetrics.join(', ')}`);
      }
    }

    return errors;
  }
}

// ==================== 格式化工具 ====================

export class FormatHelper {
  static formatDate(dateString: string, format: 'full' | 'short' | 'time' = 'full'): string {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      return '无效日期';
    }

    switch (format) {
      case 'short':
        return date.toLocaleDateString('zh-CN');
      case 'time':
        return date.toLocaleTimeString('zh-CN');
      case 'full':
      default:
        return date.toLocaleString('zh-CN');
    }
  }

  static formatDuration(seconds: number): string {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}秒`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return remainingSeconds > 0 ? `${minutes}分${remainingSeconds.toFixed(0)}秒` : `${minutes}分钟`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const remainingMinutes = Math.floor((seconds % 3600) / 60);
      return remainingMinutes > 0 ? `${hours}小时${remainingMinutes}分钟` : `${hours}小时`;
    }
  }

  static formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';

    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  }

  static formatNumber(num: number, decimals: number = 2): string {
    return Number(num).toLocaleString('zh-CN', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  static formatPercentage(value: number, decimals: number = 1): string {
    return `${(value * 100).toFixed(decimals)}%`;
  }

  static truncateText(text: string, maxLength: number, suffix: string = '...'): string {
    if (text.length <= maxLength) {
      return text;
    }
    return text.substring(0, maxLength - suffix.length) + suffix;
  }
}

// ==================== 状态管理工具 ====================

export class StatusHelper {
  static getStatusColor(status: string): string {
    const statusColors: Record<string, string> = {
      pending: '#faad14',
      running: '#1890ff',
      completed: '#52c41a',
      failed: '#ff4d4f',
      cancelled: '#8c8c8c'
    };
    return statusColors[status] || '#d9d9d9';
  }

  static getStatusText(status: string): string {
    const statusTexts: Record<string, string> = {
      pending: '等待中',
      running: '运行中',
      completed: '已完成',
      failed: '失败',
      cancelled: '已取消'
    };
    return statusTexts[status] || status;
  }

  static isRunning(status: string): boolean {
    return status === 'running';
  }

  static isCompleted(status: string): boolean {
    return status === 'completed';
  }

  static isFailed(status: string): boolean {
    return status === 'failed';
  }

  static canDelete(status: string): boolean {
    return !['running'].includes(status);
  }

  static canCancel(status: string): boolean {
    return ['pending', 'running'].includes(status);
  }
}

// ==================== 本地存储工具 ====================

export class StorageHelper {
  private static readonly PREFIX = 'rag-evaluation-';

  static set<T>(key: string, value: T): void {
    try {
      localStorage.setItem(`${StorageHelper.PREFIX}${key}`, JSON.stringify(value));
    } catch (error) {
      console.warn('Failed to save to localStorage:', error);
    }
  }

  static get<T>(key: string, defaultValue?: T): T | null {
    try {
      const item = localStorage.getItem(`${StorageHelper.PREFIX}${key}`);
      return item ? JSON.parse(item) : defaultValue ?? null;
    } catch (error) {
      console.warn('Failed to read from localStorage:', error);
      return defaultValue ?? null;
    }
  }

  static remove(key: string): void {
    try {
      localStorage.removeItem(`${StorageHelper.PREFIX}${key}`);
    } catch (error) {
      console.warn('Failed to remove from localStorage:', error);
    }
  }

  static clear(): void {
    try {
      const keys = Object.keys(localStorage);
      keys.forEach(key => {
        if (key.startsWith(StorageHelper.PREFIX)) {
          localStorage.removeItem(key);
        }
      });
    } catch (error) {
      console.warn('Failed to clear localStorage:', error);
    }
  }
}

// ==================== 通知工具 ====================

export interface NotificationOptions {
  type: 'success' | 'error' | 'warning' | 'info';
  title?: string;
  duration?: number;
  showProgress?: boolean;
}

export class NotificationHelper {
  // 这里可以根据使用的UI库（如Ant Design）来实现具体的通知功能
  // 示例实现：
  static show(message: string, options: Partial<NotificationOptions> = {}): void {
    const { type = 'info', title, duration = 3000 } = options;

    console.log(`[${type.toUpperCase()}] ${title ? `${title}: ` : ''}${message}`);

    // 如果使用Ant Design，可以这样实现：
    // import { notification } from 'antd';
    // notification[type]({
    //   message: title,
    //   description: message,
    //   duration: duration / 1000
    // });
  }

  static success(message: string, title?: string): void {
    NotificationHelper.show(message, { type: 'success', title });
  }

  static error(message: string, title?: string): void {
    NotificationHelper.show(message, { type: 'error', title, duration: 5000 });
  }

  static warning(message: string, title?: string): void {
    NotificationHelper.show(message, { type: 'warning', title });
  }

  static info(message: string, title?: string): void {
    NotificationHelper.show(message, { type: 'info', title });
  }
}

// ==================== 防抖和节流工具 ====================

export class DebounceHelper {
  static debounce<T extends (...args: any[]) => any>(
    func: T,
    wait: number
  ): (...args: Parameters<T>) => void {
    let timeout: NodeJS.Timeout;

    return (...args: Parameters<T>) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => func(...args), wait);
    };
  }

  static throttle<T extends (...args: any[]) => any>(
    func: T,
    limit: number
  ): (...args: Parameters<T>) => void {
    let inThrottle: boolean;

    return (...args: Parameters<T>) => {
      if (!inThrottle) {
        func(...args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  }
}

// ==================== 批量操作工具 ====================

export class BatchHelper {
  static async processBatch<T, R>(
    items: T[],
    processor: (item: T) => Promise<R>,
    options: {
      batchSize?: number;
      onProgress?: (completed: number, total: number) => void;
      onError?: (item: T, error: any) => void;
    } = {}
  ): Promise<{ results: R[]; errors: Array<{ item: T; error: any }> }> {
    const { batchSize = 5, onProgress, onError } = options;
    const results: R[] = [];
    const errors: Array<{ item: T; error: any }> = [];
    let completed = 0;

    for (let i = 0; i < items.length; i += batchSize) {
      const batch = items.slice(i, i + batchSize);

      const batchPromises = batch.map(async (item) => {
        try {
          const result = await processor(item);
          results.push(result);
          completed++;
          onProgress?.(completed, items.length);
          return result;
        } catch (error) {
          errors.push({ item, error });
          completed++;
          onProgress?.(completed, items.length);
          onError?.(item, error);
          throw error;
        }
      });

      await Promise.allSettled(batchPromises);
    }

    return { results, errors };
  }
}

// ==================== 导出所有工具类 ====================
// 已通过 export class 方式导出，无需重复导出