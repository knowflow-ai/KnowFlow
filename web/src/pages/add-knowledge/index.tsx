import { useKnowledgeBaseId } from '@/hooks/knowledge-hooks';
import {
  useNavigateWithFromState,
  useSecondPathName,
  useThirdPathName,
} from '@/hooks/route-hook';
import { Breadcrumb } from 'antd';
import { ItemType } from 'antd/es/breadcrumb/Breadcrumb';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Outlet } from 'umi';
import Siderbar from './components/knowledge-sidebar';
import { KnowledgeDatasetRouteKey, KnowledgeRouteKey } from './constant';
import styles from './index.less';

const KnowledgeAdding = () => {
  const knowledgeBaseId = useKnowledgeBaseId();

  const { t } = useTranslation();
  const activeKey: KnowledgeRouteKey =
    (useSecondPathName() as KnowledgeRouteKey) || KnowledgeRouteKey.Dataset;

  const datasetActiveKey: KnowledgeDatasetRouteKey =
    useThirdPathName() as KnowledgeDatasetRouteKey;

  const gotoList = useNavigateWithFromState();

  // 如果没有知识库ID，显示错误信息
  if (!knowledgeBaseId) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h3>知识库ID缺失</h3>
        <p>请检查URL参数是否正确</p>
        <button
          onClick={() => gotoList('/knowledge')}
          style={{ marginTop: '10px', padding: '8px 16px' }}
        >
          返回知识库列表
        </button>
      </div>
    );
  }

  const breadcrumbItems: ItemType[] = useMemo(() => {
    const items: ItemType[] = [
      {
        title: (
          <a onClick={() => gotoList('/knowledge')}>
            {t('header.knowledgeBase')}
          </a>
        ),
      },
      {
        title: datasetActiveKey ? (
          <Link
            to={`/knowledge/${KnowledgeRouteKey.Dataset}?id=${knowledgeBaseId}`}
          >
            {t(`knowledgeDetails.${activeKey}`)}
          </Link>
        ) : (
          t(`knowledgeDetails.${activeKey}`)
        ),
      },
    ];

    if (datasetActiveKey) {
      items.push({
        title: t(`knowledgeDetails.${datasetActiveKey}`),
      });
    }

    return items;
  }, [activeKey, datasetActiveKey, gotoList, knowledgeBaseId, t]);

  return (
    <>
      <div className={styles.container}>
        <Siderbar></Siderbar>
        <div className={styles.contentWrapper}>
          <Breadcrumb items={breadcrumbItems} />
          <div className={styles.content}>
            <Outlet></Outlet>
          </div>
        </div>
      </div>
    </>
  );
};

export default KnowledgeAdding;
