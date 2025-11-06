import React from 'react';
import { DeleteOutlined } from '@ant-design/icons';

interface BatchActionBarProps {
  selectedCount: number;
  onDelete: () => void;
  onCancel: () => void;
  deleting?: boolean;
  itemName?: string;
}

export const BatchActionBar: React.FC<BatchActionBarProps> = ({
  selectedCount,
  onDelete,
  onCancel,
  deleting = false,
  itemName = '项',
}) => {
  if (selectedCount === 0) return null;

  return (
    <div
      style={{
        marginBottom: 16,
        padding: '8px 16px',
        background: '#f5f5f5',
        borderRadius: 6,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <span>已选择 {selectedCount} 项</span>
      <button
        type="button"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 12px',
          background: '#ff4d4f',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          cursor: deleting ? 'not-allowed' : 'pointer',
          opacity: deleting ? 0.7 : 1,
          fontSize: 14,
          transition: 'all 0.2s',
        }}
        disabled={deleting}
        onClick={onDelete}
      >
        <DeleteOutlined />
        批量删除
      </button>
      <button
        type="button"
        style={{
          padding: '6px 12px',
          background: '#fff',
          color: '#666',
          border: '1px solid #d9d9d9',
          borderRadius: 6,
          cursor: 'pointer',
          fontSize: 14,
          transition: 'all 0.2s',
        }}
        onClick={onCancel}
      >
        取消选择
      </button>
    </div>
  );
};