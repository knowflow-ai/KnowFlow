import { useTranslate } from '@/hooks/common-hooks';
import { Form, Select } from 'antd';

const SplitLevel = () => {
  const { t } = useTranslate('knowledgeConfiguration');

  const options = [
    { label: 'H1', value: 1 },
    { label: 'H2', value: 2 },
    { label: 'H3', value: 3 },
    { label: 'H4', value: 4 },
    { label: 'H5', value: 5 },
    { label: 'H6', value: 6 },
  ];

  return (
    <Form.Item
      name={['parser_config', 'split_level']}
      label={t('splitLevel')}
      initialValue={2}
      tooltip={t('splitLevelTip')}
    >
      <Select options={options} />
    </Form.Item>
  );
};

export default SplitLevel;
