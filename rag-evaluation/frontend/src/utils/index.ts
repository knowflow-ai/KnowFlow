/**
 * 工具函数集合
 */

// 格式化日期时间
export const formatDateTime = (dateStr: string | Date, format: string = 'YYYY-MM-DD HH:mm:ss'): string => {
  const date = typeof dateStr === 'string' ? new Date(dateStr) : dateStr;

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');

  return format
    .replace('YYYY', String(year))
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds);
};

// 格式化文件大小
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
};

// 计算百分比
export const calculatePercentage = (value: number, total: number): number => {
  if (total === 0) return 0;
  return Math.round((value / total) * 100);
};

// 获取评分等级
export const getScoreLevel = (score: number): {
  level: string;
  color: string;
  description: string;
} => {
  if (score >= 90) {
    return {
      level: '优秀',
      color: '#52c41a',
      description: '系统表现优异，完全满足要求',
    };
  } else if (score >= 80) {
    return {
      level: '良好',
      color: '#1890ff',
      description: '系统表现良好，基本满足要求',
    };
  } else if (score >= 70) {
    return {
      level: '中等',
      color: '#faad14',
      description: '系统表现一般，有改进空间',
    };
  } else if (score >= 60) {
    return {
      level: '及格',
      color: '#fa8c16',
      description: '系统勉强达标，需要改进',
    };
  } else {
    return {
      level: '不及格',
      color: '#ff4d4f',
      description: '系统表现不佳，亟需优化',
    };
  }
};

// 生成唯一 ID
export const generateUniqueId = (): string => {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

// 防抖函数
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) {
      clearTimeout(timeout);
    }

    timeout = setTimeout(() => {
      func(...args);
    }, wait);
  };
};

// 节流函数
export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle: boolean = false;

  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  };
};

// 深拷贝
export const deepClone = <T>(obj: T): T => {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }

  if (obj instanceof Date) {
    return new Date(obj.getTime()) as any;
  }

  if (obj instanceof Array) {
    return obj.map(item => deepClone(item)) as any;
  }

  if (obj instanceof Object) {
    const clonedObj = {} as T;
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        (clonedObj as any)[key] = deepClone(obj[key]);
      }
    }
    return clonedObj;
  }

  return obj;
};

// 下载文件
export const downloadFile = (blob: Blob, filename: string): void => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

// 解析 CSV 内容
export const parseCSV = (content: string): Array<Record<string, any>> => {
  const lines = content.split('\n').filter(line => line.trim());
  if (lines.length === 0) return [];

  const headers = lines[0].split(',').map(h => h.trim());
  const results = [];

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',').map(v => v.trim());
    const obj: Record<string, any> = {};

    headers.forEach((header, index) => {
      obj[header] = values[index] || '';
    });

    results.push(obj);
  }

  return results;
};

// 验证邮箱格式
export const validateEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

// 验证 URL 格式
export const validateUrl = (url: string): boolean => {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
};

// 格式化数字（添加千分位）
export const formatNumber = (num: number): string => {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
};

// 计算时间差
export const getTimeDiff = (startTime: string | Date, endTime: string | Date): string => {
  const start = typeof startTime === 'string' ? new Date(startTime) : startTime;
  const end = typeof endTime === 'string' ? new Date(endTime) : endTime;

  const diff = end.getTime() - start.getTime();

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    return `${days}天${hours % 24}小时`;
  } else if (hours > 0) {
    return `${hours}小时${minutes % 60}分钟`;
  } else if (minutes > 0) {
    return `${minutes}分钟${seconds % 60}秒`;
  } else {
    return `${seconds}秒`;
  }
};

// 获取文件扩展名
export const getFileExtension = (filename: string): string => {
  const parts = filename.split('.');
  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : '';
};

// 判断文件类型
export const getFileType = (filename: string): string => {
  const ext = getFileExtension(filename);

  const typeMap: Record<string, string> = {
    'csv': 'CSV',
    'json': 'JSON',
    'jsonl': 'JSONL',
    'xlsx': 'Excel',
    'xls': 'Excel',
    'txt': 'Text',
    'md': 'Markdown',
    'pdf': 'PDF',
  };

  return typeMap[ext] || 'Unknown';
};

// 颜色工具
export const colors = {
  success: '#52c41a',
  warning: '#faad14',
  error: '#ff4d4f',
  info: '#1890ff',
  default: '#d9d9d9',
};

// 指标名称映射 - 只保留5个核心RAGAS指标
export const metricNameMap: Record<string, string> = {
  'faithfulness': '忠实度',
  'answer_correctness': '答案正确性',
  'context_precision': '上下文精准度',
  'context_recall': '上下文召回率',
  'answer_relevancy': '答案相关性',
};

// 获取指标显示名称
export const getMetricDisplayName = (metricKey: string): string => {
  return metricNameMap[metricKey] || metricKey;
};

// 状态颜色映射
export const statusColorMap: Record<string, string> = {
  'pending': 'default',
  'running': 'processing',
  'completed': 'success',
  'failed': 'error',
  'cancelled': 'warning',
};

// 导出所有工具
export default {
  formatDateTime,
  formatFileSize,
  calculatePercentage,
  getScoreLevel,
  generateUniqueId,
  debounce,
  throttle,
  deepClone,
  downloadFile,
  parseCSV,
  validateEmail,
  validateUrl,
  formatNumber,
  getTimeDiff,
  getFileExtension,
  getFileType,
  colors,
  metricNameMap,
  getMetricDisplayName,
  statusColorMap,
};