import { useTranslate } from '@/hooks/common-hooks';
import { Form, Switch } from 'antd';

const EnableHeadingInContent = () => {
  const { t } = useTranslate('knowledgeDetails');

  return (
    <Form.Item
      name={['parser_config', 'enable_heading_in_content']}
      label={t('enableHeadingInContent', '包含父标题')}
      initialValue={false}
      tooltip={t(
        'enableHeadingInContentTip',
        '为每个分块添加父级标题（Markdown格式，如：# 第一章\n## 第一节），有助于LLM理解文档结构和上下文',
      )}
      valuePropName="checked"
    >
      <Switch />
    </Form.Item>
  );
};

export default EnableHeadingInContent;
