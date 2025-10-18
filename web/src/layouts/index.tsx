import { Layout, theme } from 'antd';
import React from 'react';
import { Outlet } from 'umi';
import '../locales/config';
import Header from './components/header';

import styles from './index.less';

const { Content, Sider } = Layout;

const App: React.FC = () => {
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  return (
    <Layout className={styles.layout}>
      <Sider width="150px" className={styles.siderStyle}>
        <Header></Header>
      </Sider>
      <Layout className={styles.mainLayout}>
        <Content className={styles.contentStyle}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;
