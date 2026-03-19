import SvgIcon from '@/components/svg-icon';
import {
  useFetchSystemStatus,
  useFetchSystemVersion,
} from '@/hooks/user-setting-hooks';
import {
  ISystemStatus,
  TaskExecutorHeartbeatItem,
} from '@/interfaces/database/user-setting';
import { Badge, Card, Flex, Spin, Typography } from 'antd';
import classNames from 'classnames';
import lowerCase from 'lodash/lowerCase';
import upperFirst from 'lodash/upperFirst';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import { toFixed } from '@/utils/common-util';
import { isObject } from 'lodash';
import styles from './index.less';
import TaskBarChat from './task-bar-chat';

const { Text } = Typography;

enum Status {
  'green' = 'success',
  'red' = 'error',
  'yellow' = 'warning',
}

const TitleMap = {
  doc_engine: 'Doc Engine',
  storage: 'Object Storage',
  redis: 'Redis',
  database: 'Database',
  task_executor_heartbeats: 'Task Executor',
};

const IconMap = {
  es: 'es',
  doc_engine: 'storage',
  redis: 'redis',
  storage: 'minio',
  database: 'database',
};

const SystemInfo = () => {
  const { t } = useTranslation();
  const {
    systemStatus,
    fetchSystemStatus,
    loading: statusLoading,
  } = useFetchSystemStatus();
  const {
    version,
    fetchSystemVersion,
    loading: versionLoading,
  } = useFetchSystemVersion();

  useEffect(() => {
    fetchSystemStatus();
    fetchSystemVersion();
  }, [fetchSystemStatus, fetchSystemVersion]);

  return (
    <section className={styles.systemInfo}>
      <Spin spinning={statusLoading || versionLoading}>
        <Flex gap={16} vertical>
          {/* 系统版本信息 */}
          <Card
            type="inner"
            title={
              <Flex align="center" gap={10}>
                <img src="/logo.svg" alt="" width={26} />
                <span className={styles.title}>
                  {t('setting.systemVersion')}
                </span>
              </Flex>
            }
          >
            <Flex align="center" gap={16} className={styles.text}>
              <b>{t('setting.currentVersion')}:</b>
              <Text>{version || 'Loading...'}</Text>
            </Flex>
          </Card>
          {Object.keys(systemStatus).map((key) => {
            const info = systemStatus[key as keyof ISystemStatus];

            return (
              <Card
                type="inner"
                title={
                  <Flex align="center" gap={10}>
                    {key === 'task_executor_heartbeats' ? (
                      <img src="/logo.svg" alt="" width={26} />
                    ) : (
                      <SvgIcon
                        name={IconMap[key as keyof typeof IconMap]}
                        width={26}
                      ></SvgIcon>
                    )}
                    <span className={styles.title}>
                      {TitleMap[key as keyof typeof TitleMap]}
                    </span>
                    <Badge
                      className={styles.badge}
                      status={Status[info.status as keyof typeof Status]}
                    />
                  </Flex>
                }
                key={key}
              >
                {key === 'task_executor_heartbeats' ? (
                  isObject(info) ? (
                    <TaskBarChat
                      data={info as Record<string, TaskExecutorHeartbeatItem[]>}
                    ></TaskBarChat>
                  ) : (
                    <Text className={styles.error}>
                      {typeof info.error === 'string' ? info.error : ''}
                    </Text>
                  )
                ) : (
                  Object.keys(info)
                    .filter((x) => x !== 'status')
                    .map((x) => {
                      return (
                        <Flex
                          key={x}
                          align="center"
                          gap={16}
                          className={styles.text}
                        >
                          <b>{upperFirst(lowerCase(x))}:</b>
                          <Text
                            className={classNames({
                              [styles.error]: x === 'error',
                            })}
                          >
                            {toFixed((info as Record<string, any>)[x]) as any}
                            {x === 'elapsed' && ' ms'}
                          </Text>
                        </Flex>
                      );
                    })
                )}
              </Card>
            );
          })}
        </Flex>
      </Spin>
    </section>
  );
};

export default SystemInfo;
