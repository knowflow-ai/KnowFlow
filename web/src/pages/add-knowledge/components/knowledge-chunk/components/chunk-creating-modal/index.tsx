import EditTag from '@/components/edit-tag';
import {
  useFetchChunk,
  useFetchParentChunk,
  useUpdateParentChunk,
} from '@/hooks/chunk-hooks';
import { IModalProps } from '@/interfaces/common';
import { IChunk } from '@/interfaces/database/knowledge';
import { DeleteOutlined } from '@ant-design/icons';
import { Col, Divider, Form, Input, Modal, Row, Space, Switch } from 'antd';
import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useDeleteChunkByIds } from '../../hooks';
import {
  transformTagFeaturesArrayToObject,
  transformTagFeaturesObjectToArray,
} from '../../utils';
import { TagFeatureItem } from './tag-feature-item';

type FieldType = Pick<
  IChunk,
  'content_with_weight' | 'tag_kwd' | 'question_kwd' | 'important_kwd'
>;

interface kFProps {
  doc_id: string;
  chunkId: string | undefined;
  parserId: string;
}

const ChunkCreatingModal: React.FC<IModalProps<any> & kFProps> = ({
  doc_id,
  chunkId,
  hideModal,
  onOk,
  loading,
  parserId,
}) => {
  const [form] = Form.useForm();
  const [parentForm] = Form.useForm();
  const [checked, setChecked] = useState(false);
  const [parentChunkId, setParentChunkId] = useState<string | undefined>();
  const { removeChunk } = useDeleteChunkByIds();
  const { data } = useFetchChunk(chunkId);
  const { data: parentData, loading: parentLoading } = useFetchParentChunk(
    parentChunkId,
    doc_id,
  );
  const { updateParentChunk, loading: parentUpdateLoading } =
    useUpdateParentChunk();
  const { t } = useTranslation();

  const isTagParser = parserId === 'tag';

  const handleOk = useCallback(async () => {
    try {
      const values = await form.validateFields();

      // 如果存在父块，同时保存父块
      if (parentChunkId) {
        const parentValues = await parentForm.validateFields();
        await updateParentChunk({
          doc_id,
          parent_chunk_id: parentChunkId,
          content_with_weight: parentValues.content_with_weight,
        });
      }

      onOk?.({
        ...values,
        tag_feas: transformTagFeaturesArrayToObject(values.tag_feas),
        available_int: checked ? 1 : 0,
      });
    } catch (errorInfo) {
      console.log('Failed:', errorInfo);
    }
  }, [
    checked,
    form,
    parentForm,
    parentChunkId,
    updateParentChunk,
    doc_id,
    onOk,
  ]);

  const handleRemove = useCallback(() => {
    if (chunkId) {
      return removeChunk([chunkId], doc_id);
    }
  }, [chunkId, doc_id, removeChunk]);

  const handleCheck = useCallback(() => {
    setChecked(!checked);
  }, [checked]);

  useEffect(() => {
    if (data?.code === 0) {
      const { available_int, tag_feas, parent_chunk_id } = data.data;

      form.setFieldsValue({
        ...(data.data || {}),
        tag_feas: transformTagFeaturesObjectToArray(tag_feas),
      });

      setChecked(available_int !== 0);
      setParentChunkId(parent_chunk_id);
    }
  }, [data, form, chunkId]);

  useEffect(() => {
    if (parentData) {
      parentForm.setFieldsValue({
        content_with_weight: parentData.content_with_weight,
      });
    }
  }, [parentData, parentForm]);

  const hasParentChunk = !!(chunkId && parentChunkId);

  return (
    <Modal
      title={`${chunkId ? t('common.edit') : t('common.create')} ${t('chunk.chunk')}`}
      open={true}
      onOk={handleOk}
      onCancel={hideModal}
      okButtonProps={{ loading: loading || parentUpdateLoading }}
      destroyOnClose
      width={hasParentChunk ? 1000 : 600}
    >
      <Row gutter={24}>
        {/* 子块编辑区域 */}
        <Col span={hasParentChunk ? 12 : 24}>
          {hasParentChunk && (
            <div style={{ marginBottom: 16, fontWeight: 500, fontSize: 14 }}>
              {t('chunk.childChunk')}
            </div>
          )}
          <Form form={form} autoComplete="off" layout={'vertical'}>
            <Form.Item<FieldType>
              label={t('chunk.chunk')}
              name="content_with_weight"
              rules={[{ required: true, message: t('chunk.chunkMessage') }]}
            >
              <Input.TextArea autoSize={{ minRows: 4, maxRows: 10 }} />
            </Form.Item>

            <Form.Item<FieldType>
              label={t('chunk.keyword')}
              name="important_kwd"
            >
              <EditTag></EditTag>
            </Form.Item>
            <Form.Item<FieldType>
              label={t('chunk.question')}
              name="question_kwd"
              tooltip={t('chunk.questionTip')}
            >
              <EditTag></EditTag>
            </Form.Item>
            {isTagParser && (
              <Form.Item<FieldType>
                label={t('knowledgeConfiguration.tagName')}
                name="tag_kwd"
              >
                <EditTag></EditTag>
              </Form.Item>
            )}

            {!isTagParser && <TagFeatureItem></TagFeatureItem>}
          </Form>
        </Col>

        {/* 父块编辑区域 */}
        {hasParentChunk && (
          <Col span={12}>
            <div style={{ marginBottom: 16, fontWeight: 500, fontSize: 14 }}>
              {t('chunk.parentChunk')}
            </div>
            <Form form={parentForm} layout="vertical">
              <Form.Item
                label={t('chunk.parentChunkContent')}
                name="content_with_weight"
              >
                <Input.TextArea autoSize={{ minRows: 4, maxRows: 10 }} />
              </Form.Item>
            </Form>
          </Col>
        )}
      </Row>

      {chunkId && (
        <section>
          <Divider></Divider>
          <Space size={'large'}>
            <Switch
              checkedChildren={t('chunk.enabled')}
              unCheckedChildren={t('chunk.disabled')}
              onChange={handleCheck}
              checked={checked}
            />

            <span onClick={handleRemove}>
              <DeleteOutlined /> {t('common.delete')}
            </span>
          </Space>
        </section>
      )}
    </Modal>
  );
};
export default ChunkCreatingModal;
