import { useState, useCallback } from 'react';
import { message, Modal, App } from 'antd';

interface BatchDeleteOptions {
  apiCall: (ids: string[]) => Promise<{
    message: string;
    deleted_count: number;
    total_count: number;
    failed_count: number;
    failed_ids?: string[];
    running_tasks?: string[];
    running_count?: number;
  }>;
  itemName: string;
  onSuccess?: () => void;
  skipRunning?: boolean;
  permanentWarning?: boolean;
}

export const useBatchDelete = ({
  apiCall,
  itemName,
  onSuccess,
  skipRunning = false,
  permanentWarning = true,
}: BatchDeleteOptions) => {
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const appContext = App.useApp();

  // 处理选择变化
  const onSelectChange = useCallback((newSelectedRowKeys: React.Key[]) => {
    setSelectedRowKeys(newSelectedRowKeys);
  }, []);

  // 清空选择
  const clearSelection = useCallback(() => {
    setSelectedRowKeys([]);
  }, []);

  // 批量删除处理
  const handleBatchDelete = useCallback(async () => {
    console.log('🗑️ 批量删除开始，选中项目:', selectedRowKeys.length);

    if (selectedRowKeys.length === 0) {
      message.warning(`请选择要删除的${itemName}`);
      return;
    }

    console.log('🗑️ 准备弹出 Modal.confirm');

  if (appContext.modal) {
    console.log('✅ 使用 appContext.modal.confirm');
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
        console.log('🗑️ 用户确认批量删除，开始调用API...');
        setBatchDeleting(true);
        try {
          const response = await apiCall(selectedRowKeys as string[]);

          // 成功删除
          if (response.deleted_count > 0) {
            message.success(response.message || `成功删除 ${response.deleted_count} 个${itemName}`);
            clearSelection();
            onSuccess?.();
          }

          // 删除失败
          if (response.failed_count > 0) {
            message.warning(`${response.failed_count} 个${itemName}删除失败`);
          }

          // 运行中的任务跳过
          if (response.running_count && response.running_count > 0) {
            message.info(`${response.running_count} 个运行中的${itemName}已跳过`);
          }
        } catch (error) {
          console.error('Batch delete failed:', error);
          message.error('批量删除失败');
        } finally {
          setBatchDeleting(false);
        }
      },
      onCancel: () => {
        console.log('🗑️ 用户取消批量删除');
      },
    });
  } else {
    console.log('❌ modal 不存在，回退到静态 Modal.confirm');
    // 回退到静态方法
    Modal.confirm({
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
        console.log('🗑️ 用户确认批量删除，开始调用API...');
        setBatchDeleting(true);
        try {
          const response = await apiCall(selectedRowKeys as string[]);

          // 成功删除
          if (response.deleted_count > 0) {
            message.success(response.message || `成功删除 ${response.deleted_count} 个${itemName}`);
            clearSelection();
            onSuccess?.();
          }

          // 删除失败
          if (response.failed_count > 0) {
            message.warning(`${response.failed_count} 个${itemName}删除失败`);
          }

          // 运行中的任务跳过
          if (response.running_count && response.running_count > 0) {
            message.info(`${response.running_count} 个运行中的${itemName}已跳过`);
          }
        } catch (error) {
          console.error('Batch delete failed:', error);
          message.error('批量删除失败');
        } finally {
          setBatchDeleting(false);
        }
      },
      onCancel: () => {
        console.log('🗑️ 用户取消批量删除');
      },
    });
  }

    console.log('🗑️ Modal.confirm 已调用');
  }, [selectedRowKeys, apiCall, itemName, permanentWarning, skipRunning, clearSelection, onSuccess, appContext]);

  // 行选择配置
  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
    // 可选的自定义禁用逻辑
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
};