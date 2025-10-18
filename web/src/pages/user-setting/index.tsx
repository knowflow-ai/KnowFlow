import { Flex } from 'antd';
import { Outlet } from 'umi';
import SideBar from './sidebar';

import styles from './index.less';

const UserSetting = () => {
  return (
    <Flex className={styles.settingWrapper}>
      <div className={styles.sidebarSection}>
        <SideBar></SideBar>
      </div>
      <div className={styles.divider}></div>
      <Flex flex={1} className={styles.outletWrapper}>
        <Outlet></Outlet>
      </Flex>
    </Flex>
  );
};

export default UserSetting;
