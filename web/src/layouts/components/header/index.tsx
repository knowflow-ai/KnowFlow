// import { ReactComponent as FileIcon } from '@/assets/svg/file-management.svg';
// import { ReactComponent as GraphIcon } from '@/assets/svg/graph.svg';
// import { ReactComponent as KnowledgeBaseIcon } from '@/assets/svg/knowledge-base.svg';

import logo from '@/assets/image/logo.svg';
import { ReactComponent as Chat } from '@/assets/svg/leftBar/chat.svg';
import { ReactComponent as ChatActive } from '@/assets/svg/leftBar/chatActive.svg';
import { ReactComponent as File } from '@/assets/svg/leftBar/file.svg';
import { ReactComponent as FileActive } from '@/assets/svg/leftBar/fileActive.svg';
import { ReactComponent as Flow } from '@/assets/svg/leftBar/flow.svg';
import { ReactComponent as FlowActive } from '@/assets/svg/leftBar/flowActive.svg';
import { ReactComponent as Knowledge } from '@/assets/svg/leftBar/knowledge.svg';
import { ReactComponent as KnowledgeActive } from '@/assets/svg/leftBar/knowledgeActive.svg';
import { ReactComponent as Search } from '@/assets/svg/leftBar/search.svg';
import { ReactComponent as SearchActive } from '@/assets/svg/leftBar/searchActive.svg';

import { useTranslate } from '@/hooks/common-hooks';
import { useFetchAppConf } from '@/hooks/logic-hooks';
import { useNavigateWithFromState } from '@/hooks/route-hook';
// import { MessageOutlined, SearchOutlined } from '@ant-design/icons';
import { Layout, Space, theme } from 'antd';
import { MouseEventHandler, useCallback, useMemo } from 'react';
import { useLocation } from 'umi';
import Toolbar from '../right-toolbar';

import { useTheme } from '@/components/theme-provider';
import styles from './index.less';

const { Header } = Layout;

const RagHeader = () => {
  const {
    token: { colorBgContainer },
  } = theme.useToken();
  const navigate = useNavigateWithFromState();
  const { pathname } = useLocation();
  const { t } = useTranslate('header');
  const appConf = useFetchAppConf();
  const { theme: themeRag } = useTheme();
  const tagsData = useMemo(
    () => [
      { path: '/chat', name: t('chat'), icon: Chat, iconActive: ChatActive },
      {
        path: '/knowledge',
        name: t('knowledgeBase'),
        icon: Knowledge,
        iconActive: KnowledgeActive,
      },
      {
        path: '/search',
        name: t('search'),
        icon: Search,
        iconActive: SearchActive,
      },
      // { path: '/flow', name: t('flow'), icon: Flow, iconActive: FlowActive },
      {
        path: '/agent-list',
        name: t('flow'),
        icon: Flow,
        iconActive: FlowActive,
      },
      {
        path: '/file',
        name: t('fileManager'),
        icon: File,
        iconActive: FileActive,
      },
    ],
    [t],
  );

  const currentPath = useMemo(() => {
    return (
      tagsData.find((x) => pathname.startsWith(x.path))?.name || 'knowledge'
    );
  }, [pathname, tagsData]);

  const handleChange = useCallback(
    (path: string): MouseEventHandler =>
      (e) => {
        e.preventDefault();
        navigate(path);
      },
    [navigate],
  );

  const handleLogoClick = useCallback(() => {
    navigate('/');
  }, [navigate]);

  return (
    <Header
      style={{
        padding: '0 16px',
        // background: colorBgContainer,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        alignItems: 'center',
        height: '72px',
      }}
    >
      <div>
        <Space
          size={12}
          onClick={handleLogoClick}
          className={styles.logoWrapper}
        >
          <img src={logo} alt="KnowFlow" className={styles.appIcon} />
          {/* <span className={styles.appName}>{appConf.appName}</span> */}
        </Space>
      </div>
      <Space size={[0, 8]} wrap>
        <div className={styles.ragContent}>
          {tagsData.map((item, index) => (
            <div
              className={
                item.name === currentPath
                  ? styles.ragItemActive
                  : styles.ragItem
              }
              key={item.name}
            >
              <a onClick={handleChange(item.path)}>
                {item.name === currentPath ? (
                  <item.iconActive
                    className={styles.radioButtonIcon}
                  ></item.iconActive>
                ) : (
                  <item.icon className={styles.radioButtonIcon}></item.icon>
                )}
                <div className={styles.ragText}>{item.name}</div>
              </a>
            </div>
          ))}
        </div>
        {/* <Radio.Group
          defaultValue="a"
          buttonStyle="solid"
          className={
            themeRag === 'dark' ? styles.radioGroupDark : styles.radioGroup
          }
          value={currentPath}
        >
          {tagsData.map((item, index) => (
            <Radio.Button
              className={`${themeRag === 'dark' ? 'dark' : 'light'} ${index === 0 ? 'first' : ''} ${index === tagsData.length - 1 ? 'last' : ''}`}
              value={item.name}
              key={item.name}
            >
              <a href={item.path}>
                <Flex
                  align="center"
                  gap={8}
                  onClick={handleChange(item.path)}
                  className="cursor-pointer"
                >
                  <item.icon
                    className={styles.radioButtonIcon}
                    stroke={item.name === currentPath ? 'black' : 'white'}
                  ></item.icon>
                  {item.name}
                </Flex>
              </a>
            </Radio.Button>
          ))}
        </Radio.Group> */}
      </Space>
      <Toolbar></Toolbar>
    </Header>
  );
};

export default RagHeader;
