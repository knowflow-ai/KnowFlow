import { Flex } from 'antd';
import { Outlet } from 'umi';
import SideBar from './sidebar';

import styles from './index.less';

const UserSetting = () => {
  return (
    <Flex className={styles.settingWrapper} style={{ padding: '20px' }}>
      <SideBar></SideBar>
      <Flex flex={1} className={styles.outletWrapper}>
        <Outlet></Outlet>
      </Flex>
    </Flex>
  );
};

export default UserSetting;
