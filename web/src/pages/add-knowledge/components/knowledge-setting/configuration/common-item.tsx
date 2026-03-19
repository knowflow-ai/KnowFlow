import { useTranslate } from '@/hooks/common-hooks';
import { useHandleChunkMethodSelectChange } from '@/hooks/logic-hooks';
import { ModernLayoutRecognizers, ModernParsers } from '@/utils/parser-filter';
import { Form, Select } from 'antd';
import { memo, useEffect, useRef } from 'react';
import {
  useHasParsedDocument,
  useSelectChunkMethodList,
  useSelectEmbeddingModelOptions,
} from '../hooks';

export const EmbeddingModelItem = memo(function EmbeddingModelItem() {
  const { t } = useTranslate('knowledgeConfiguration');
  const embeddingModelOptions = useSelectEmbeddingModelOptions();
  const disabled = useHasParsedDocument();

  return (
    <Form.Item
      name="embd_id"
      label={t('embeddingModel')}
      rules={[{ required: true }]}
      tooltip={t('embeddingModelTip')}
    >
      <Select
        placeholder={t('embeddingModelPlaceholder')}
        options={embeddingModelOptions}
        disabled={disabled}
      ></Select>
    </Form.Item>
  );
});

export const ChunkMethodItem = memo(function ChunkMethodItem() {
  const { t } = useTranslate('knowledgeConfiguration');
  const form = Form.useFormInstance();
  const handleChunkMethodSelectChange = useHandleChunkMethodSelectChange(form);
  const disabled = useHasParsedDocument();

  // Watch layout_recognize value from parser_config
  const layoutRecognize = Form.useWatch(
    ['parser_config', 'layout_recognize'],
    form,
  );
  const currentParserId = Form.useWatch('parser_id', form);
  const parserList = useSelectChunkMethodList(layoutRecognize);

  // Use ref to track previous value and avoid triggering on initial mount
  const prevLayoutRecognizeRef = useRef<string | undefined>();
  const isInitialMount = useRef(true);

  // Auto-switch parser_id when layout_recognize changes
  useEffect(() => {
    // Skip on initial mount
    if (isInitialMount.current) {
      isInitialMount.current = false;
      prevLayoutRecognizeRef.current = layoutRecognize;
      return;
    }

    // Skip if values not ready or layout_recognize hasn't changed
    if (!layoutRecognize || !currentParserId) return;
    if (prevLayoutRecognizeRef.current === layoutRecognize) return;

    prevLayoutRecognizeRef.current = layoutRecognize;

    const isModernLayoutRecognizer =
      ModernLayoutRecognizers.includes(layoutRecognize);
    const isCurrentParserModern = ModernParsers.includes(currentParserId);

    // If layout_recognize is MinerU/DOTS/PaddleOCR but current parser is not modern, switch to smart
    if (isModernLayoutRecognizer && !isCurrentParserModern) {
      form.setFieldsValue({ parser_id: 'smart' });
      handleChunkMethodSelectChange('smart');
    }
    // If layout_recognize is not MinerU/DOTS/PaddleOCR but current parser is modern, switch to naive
    else if (!isModernLayoutRecognizer && isCurrentParserModern) {
      form.setFieldsValue({ parser_id: 'naive' });
      handleChunkMethodSelectChange('naive');
    }
  }, [layoutRecognize, currentParserId, form, handleChunkMethodSelectChange]);

  return (
    <Form.Item
      name="parser_id"
      label={t('chunkMethod')}
      tooltip={t('chunkMethodTip')}
      rules={[{ required: true }]}
    >
      <Select
        placeholder={t('chunkMethodPlaceholder')}
        disabled={disabled}
        onChange={handleChunkMethodSelectChange}
        options={parserList}
      ></Select>
    </Form.Item>
  );
});
