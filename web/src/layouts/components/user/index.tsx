import { ReactComponent as Setting } from '@/assets/svg/leftBar/setting.svg';
import { ReactComponent as SettingActive } from '@/assets/svg/leftBar/settingActive.svg';
import React from 'react';
import { history, useLocation } from 'umi';

import styles from '../header/index.less';

const App: React.FC = () => {
  const { pathname } = useLocation();
  const isActive = pathname.startsWith('/user-setting');

  const toSetting = () => {
    history.push('/user-setting');
  };

  return (
    <div
      className={isActive ? styles.ragItemActive : styles.ragItem}
      onClick={toSetting}
    >
      <a>
        {isActive ? (
          <SettingActive className={styles.radioButtonIcon}></SettingActive>
        ) : (
          <Setting className={styles.radioButtonIcon}></Setting>
        )}
        <div className={styles.ragText}>设置</div>
      </a>
    </div>
  );
};

export default App;
