import { DocumentParserType } from '@/constants/knowledge';
import { useTranslate } from '@/hooks/common-hooks';
import { InfoCircleOutlined } from '@ant-design/icons';
import {
  Alert,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Switch,
} from 'antd';
import { memo } from 'react';

interface ChunkingConfigProps {
  className?: string;
  parserType?: DocumentParserType; // 从外部传入切片方法类型（可选，用于文档级配置）
  initialValues?: {
    chunk_token_num?: number;
    regex_pattern?: string;
    enable_heading_in_content?: boolean;
    split_level?: number;
    parent_config?: {
      parent_chunk_size?: number;
      parent_chunk_overlap?: number;
      retrieval_mode?: 'parent' | 'child' | 'hybrid';
      parent_split_level?: number;
    };
    enable_vision_enhancement?: boolean;
    vision_description_format?: string;
    vision_batch_size?: number;
  };
}

export const ChunkingConfig = memo(function ChunkingConfig({
  className,
  parserType,
  initialValues = {
    chunk_token_num: 256,
    regex_pattern: '',
    enable_heading_in_content: false,
    split_level: 2,
    parent_config: {
      parent_chunk_size: 1024,
      parent_chunk_overlap: 100,
      retrieval_mode: 'parent',
      parent_split_level: 2,
    },
    enable_vision_enhancement: false,
    vision_description_format: '[图片描述]: {desc}',
    vision_batch_size: 3,
  },
}: ChunkingConfigProps) {
  const { t } = useTranslate('knowledgeConfiguration');
  const chunkTokenNum = Form.useWatch(['parser_config', 'chunk_token_num']);
  const enableVision = Form.useWatch([
    'parser_config',
    'enable_vision_enhancement',
  ]);

  // 根据切片方法类型决定展示哪些配置（如果没有传递 parserType，则不展示特殊配置）
  const isRegex = parserType === DocumentParserType.Regex;
  const isParentChild = parserType === DocumentParserType.ParentChild;

  // 判断是否显示 enable_heading_in_content（smart/title/parent-child 支持）
  const showHeadingInContent =
    parserType &&
    [
      DocumentParserType.Smart,
      DocumentParserType.Title,
      DocumentParserType.ParentChild,
    ].includes(parserType);

  // 判断是否显示 split_level（只有 title 支持）
  const showSplitLevel = parserType === DocumentParserType.Title;

  // 判断是否显示图片理解配置（smart/regex/title/parent-child 都支持）
  const showVisionConfig =
    parserType &&
    [
      DocumentParserType.Smart,
      DocumentParserType.Regex,
      DocumentParserType.Title,
      DocumentParserType.ParentChild,
    ].includes(parserType);

  return (
    <div className={className}>
      <Form.Item
        name={['parser_config', 'chunk_token_num']}
        label="分块大小"
        initialValue={initialValues.chunk_token_num}
        rules={[
          { required: true, message: '请输入分块大小' },
          {
            validator: (_, value) => {
              if (value < 50 || value > 2048) {
                return Promise.reject(new Error('分块大小必须在50-2048之间'));
              }
              return Promise.resolve();
            },
          },
        ]}
        extra="单位：tokens，范围：50-2048"
      >
        <InputNumber
          min={50}
          max={2048}
          placeholder="256"
          style={{ width: '100%' }}
        />
      </Form.Item>

      {showHeadingInContent && (
        <Form.Item
          name={['parser_config', 'enable_heading_in_content']}
          label="包含父标题"
          initialValue={initialValues.enable_heading_in_content ?? false}
          valuePropName="checked"
          tooltip="为每个分块添加父级标题路径（如：[章节: 第一章 > 第一节]），有助于在分块内容中保持上下文"
        >
          <Switch />
        </Form.Item>
      )}

      {showSplitLevel && (
        <Form.Item
          name={['parser_config', 'split_level']}
          label="标题分割层级"
          initialValue={2}
          tooltip="选择在哪个标题层级进行分块。H2 适合大多数文档结构。如果文档没有 H2 标题，系统会自动使用更高级别的标题。"
        >
          <Select style={{ width: '100%' }}>
            <Select.Option value={1}>H1</Select.Option>
            <Select.Option value={2}>H2</Select.Option>
            <Select.Option value={3}>H3</Select.Option>
            <Select.Option value={4}>H4</Select.Option>
            <Select.Option value={5}>H5</Select.Option>
            <Select.Option value={6}>H6</Select.Option>
          </Select>
        </Form.Item>
      )}

      {isRegex && (
        <Form.Item
          name={['parser_config', 'regex_pattern']}
          label="正则表达式"
          initialValue={initialValues.regex_pattern}
          rules={[
            {
              validator: (_, value) => {
                if (isRegex) {
                  if (!value || !value.trim()) {
                    return Promise.reject(
                      new Error('正则分块需要输入正则表达式'),
                    );
                  }
                  try {
                    new RegExp(value);
                    return Promise.resolve();
                  } catch (e) {
                    return Promise.reject(new Error('请输入有效的正则表达式'));
                  }
                }
                return Promise.resolve();
              },
            },
          ]}
          extra="用于匹配条文等结构化内容，例如：第[零一二三四五六七八九十百千万\\d]+条"
        >
          <Input placeholder="第[零一二三四五六七八九十百千万\\d]+条" />
        </Form.Item>
      )}

      {isParentChild && (
        <>
          <Alert
            message="AST父子分块模式说明"
            description="采用基于AST语义分析的双层分块结构。父分块按照Markdown标题层级（H1、H2、H3等）进行语义边界分割，确保语义完整性；子分块使用智能AST分块，保持语义连贯。检索时先通过子分块精确匹配，再返回对应的父分块提供完整上下文。"
            type="info"
            showIcon
            icon={<InfoCircleOutlined />}
            style={{ marginBottom: 16 }}
          />

          <Row gutter={16}>
            <Col span={12}>
              <Card
                title="父分块配置"
                size="small"
                style={{ marginBottom: 16 }}
              >
                <Form.Item
                  name={['parser_config', 'parent_config', 'parent_chunk_size']}
                  label="父分块大小"
                  initialValue={
                    initialValues.parent_config?.parent_chunk_size || 1024
                  }
                  rules={[
                    { required: true, message: '请输入父分块大小' },
                    {
                      validator: (_, value) => {
                        if (value < 200 || value > 4000) {
                          return Promise.reject(
                            new Error('父分块大小必须在200-4000之间'),
                          );
                        }
                        return Promise.resolve();
                      },
                    },
                  ]}
                  extra="单位：tokens，提供丰富上下文"
                >
                  <InputNumber
                    min={200}
                    max={4000}
                    placeholder="1024"
                    style={{ width: '100%' }}
                  />
                </Form.Item>

                <Form.Item
                  name={[
                    'parser_config',
                    'parent_config',
                    'parent_chunk_overlap',
                  ]}
                  label="父分块重叠"
                  initialValue={
                    initialValues.parent_config?.parent_chunk_overlap || 100
                  }
                  rules={[
                    {
                      validator: (_, value) => {
                        if (value < 0 || value > 500) {
                          return Promise.reject(
                            new Error('重叠大小必须在0-500之间'),
                          );
                        }
                        return Promise.resolve();
                      },
                    },
                  ]}
                  extra="单位：tokens，相邻父分块重叠"
                >
                  <InputNumber
                    min={0}
                    max={500}
                    placeholder="100"
                    style={{ width: '100%' }}
                  />
                </Form.Item>

                <Form.Item
                  name={[
                    'parser_config',
                    'parent_config',
                    'parent_split_level',
                  ]}
                  label="AST分割层级"
                  initialValue={
                    initialValues.parent_config?.parent_split_level || 2
                  }
                  rules={[
                    {
                      validator: (_, value) => {
                        if (value < 1 || value > 6) {
                          return Promise.reject(
                            new Error('标题层级必须在1-6之间'),
                          );
                        }
                        return Promise.resolve();
                      },
                    },
                  ]}
                  extra="按H1(1), H2(2), H3(3)等标题层级分割父分块"
                >
                  <Select placeholder="选择标题层级">
                    <Select.Option value={1}>H1 - 最大章节</Select.Option>
                    <Select.Option value={2}>
                      H2 - 主要章节（推荐）
                    </Select.Option>
                    <Select.Option value={3}>H3 - 子章节</Select.Option>
                    <Select.Option value={4}>H4 - 小节</Select.Option>
                    <Select.Option value={5}>H5 - 段落级</Select.Option>
                    <Select.Option value={6}>H6 - 细粒度</Select.Option>
                  </Select>
                </Form.Item>
              </Card>
            </Col>

            <Col span={12}>
              <Card
                title="子分块配置"
                size="small"
                style={{ marginBottom: 16 }}
              >
                <Form.Item
                  label="子分块大小"
                  extra="基于AST智能分块，自动保持语义完整性"
                >
                  <InputNumber
                    value={chunkTokenNum}
                    disabled
                    style={{ width: '100%' }}
                  />
                </Form.Item>

                <Form.Item
                  name={['parser_config', 'parent_config', 'retrieval_mode']}
                  label="检索模式"
                  initialValue={
                    initialValues.parent_config?.retrieval_mode || 'parent'
                  }
                  rules={[{ required: true, message: '请选择检索模式' }]}
                >
                  <Select placeholder="选择检索模式">
                    <Select.Option value="parent">
                      父分块模式（推荐）
                    </Select.Option>
                    <Select.Option value="child">子分块模式</Select.Option>
                    <Select.Option value="hybrid">混合模式</Select.Option>
                  </Select>
                </Form.Item>
              </Card>
            </Col>
          </Row>
        </>
      )}

      {/* 图片理解配置 - 适用于 smart/regex/title/parent-child */}
      {showVisionConfig && (
        <Card title="图片理解" size="small" style={{ marginTop: 16 }}>
          <Form.Item
            name={['parser_config', 'enable_vision_enhancement']}
            label="启用图片理解"
            initialValue={initialValues.enable_vision_enhancement ?? false}
            valuePropName="checked"
            tooltip="开启后会使用视觉模型自动识别图片内容并生成描述"
          >
            <Switch />
          </Form.Item>

          {enableVision && (
            <>
              <Form.Item
                name={['parser_config', 'vision_description_format']}
                label="描述格式"
                initialValue={
                  initialValues.vision_description_format ||
                  '[图片描述]: {desc}'
                }
                tooltip="{desc} 会被替换为实际的图片描述内容"
                rules={[
                  {
                    validator: (_, value) => {
                      if (
                        enableVision &&
                        (!value || !value.includes('{desc}'))
                      ) {
                        return Promise.reject(
                          new Error('描述格式必须包含 {desc} 占位符'),
                        );
                      }
                      return Promise.resolve();
                    },
                  },
                ]}
              >
                <Input placeholder="[图片描述]: {desc}" />
              </Form.Item>

              <Form.Item
                name={['parser_config', 'vision_batch_size']}
                label="批量处理大小"
                initialValue={initialValues.vision_batch_size || 3}
                tooltip="同时处理的图片数量，建议设置为1-5之间"
                rules={[
                  {
                    validator: (_, value) => {
                      if (value < 1 || value > 10) {
                        return Promise.reject(
                          new Error('批量大小必须在1-10之间'),
                        );
                      }
                      return Promise.resolve();
                    },
                  },
                ]}
                extra="单位：张，范围：1-10，值越大处理速度越快但占用资源越多"
              >
                <InputNumber
                  min={1}
                  max={10}
                  placeholder="3"
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </>
          )}
        </Card>
      )}
    </div>
  );
});

export default ChunkingConfig;
