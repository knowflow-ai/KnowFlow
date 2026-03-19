import { Form, InputNumber, Modal, Select, message } from 'antd';
import { useEffect } from 'react';

// 分块方法枚举
export const ChunkMethod = {
  SMART: 'smart',
  TITLE: 'title',
  REGEX: 'regex',
  PARENT_CHILD: 'parent_child',
} as const;

// PDF 解析器枚举
export const LayoutRecognizer = {
  DEEPDOC: 'DeepDOC',
  MINERU: 'MinerU',
  DOTS: 'DOTS',
} as const;

interface ParseConfigModalProps {
  visible: boolean;
  documentName?: string;
  defaultValues?: {
    parser_id?: string;
    layout_recognize?: string;
    chunk_token_num?: number;
  };
  onOk: (values: {
    parser_id: string;
    layout_recognize: string;
    parser_config?: Record<string, any>;
  }) => void;
  onCancel: () => void;
}

const ParseConfigModal: React.FC<ParseConfigModalProps> = ({
  visible,
  documentName,
  defaultValues,
  onOk,
  onCancel,
}) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (visible) {
      // 检查 parser_id 是否是有效的分块方法
      const validChunkMethods = Object.values(ChunkMethod);
      const parserId = defaultValues?.parser_id;
      const isValidChunkMethod =
        parserId && validChunkMethods.includes(parserId as any);

      // 总是重置为默认值或传入的值
      form.setFieldsValue({
        parser_id: isValidChunkMethod ? parserId : ChunkMethod.SMART,
        layout_recognize:
          defaultValues?.layout_recognize || LayoutRecognizer.MINERU,
        chunk_token_num: defaultValues?.chunk_token_num || 256,
      });
    }
  }, [visible, defaultValues, form]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      const { parser_id, layout_recognize, chunk_token_num } = values;

      onOk({
        parser_id,
        layout_recognize,
        parser_config: {
          chunk_token_num,
        },
      });
    } catch (error) {
      message.error('请完成必填项');
    }
  };

  return (
    <Modal
      title={`分块配置${documentName ? ` - ${documentName}` : ''}`}
      open={visible}
      onOk={handleOk}
      onCancel={onCancel}
      width={560}
      okText="保存配置"
      cancelText="取消"
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          parser_id: ChunkMethod.SMART,
          layout_recognize: LayoutRecognizer.MINERU,
          chunk_token_num: 256,
        }}
      >
        <Form.Item
          label="PDF 解析器"
          name="layout_recognize"
          rules={[{ required: true, message: '请选择 PDF 解析器' }]}
          tooltip="选择用于解析 PDF 文档的 OCR 引擎"
        >
          <Select>
            <Select.Option value={LayoutRecognizer.DEEPDOC}>
              DeepDOC (默认)
            </Select.Option>
            <Select.Option value={LayoutRecognizer.MINERU}>
              MinerU (高精度)
            </Select.Option>
            <Select.Option value={LayoutRecognizer.DOTS}>
              DOTS (视觉理解)
            </Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="分块方法"
          name="parser_id"
          rules={[{ required: true, message: '请选择分块方法' }]}
          tooltip="选择文档的分块策略"
        >
          <Select>
            <Select.Option value={ChunkMethod.SMART}>
              智能分块 (推荐)
            </Select.Option>
            <Select.Option value={ChunkMethod.TITLE}>标题分块</Select.Option>
            <Select.Option value={ChunkMethod.REGEX}>正则分块</Select.Option>
            <Select.Option value={ChunkMethod.PARENT_CHILD}>
              父子分块
            </Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          label="分块大小 (Token)"
          name="chunk_token_num"
          rules={[{ required: true, message: '请输入分块大小' }]}
          tooltip="每个分块的最大 token 数量"
        >
          <InputNumber
            min={64}
            max={2048}
            step={64}
            style={{ width: '100%' }}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default ParseConfigModal;
