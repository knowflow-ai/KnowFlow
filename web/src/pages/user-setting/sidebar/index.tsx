import { Domain } from '@/constants/common';
import { useTranslate } from '@/hooks/common-hooks';
import { useLogout } from '@/hooks/login-hooks';
import { useSecondPathName } from '@/hooks/route-hook';
import {
  useFetchSystemVersion,
  useFetchUserInfo,
} from '@/hooks/user-setting-hooks';
import type { MenuProps } from 'antd';
import { Menu } from 'antd';
import React, { useEffect, useMemo } from 'react';
import { useNavigate } from 'umi';
import {
  UserSettingBaseKey,
  UserSettingIconMap,
  UserSettingRouteKey,
} from '../constants';
import styles from './index.less';

type MenuItem = Required<MenuProps>['items'][number];

const SideBar = () => {
  const navigate = useNavigate();
  const pathName = useSecondPathName();
  const { logout } = useLogout();
  const { t } = useTranslate('setting');
  const { version, fetchSystemVersion } = useFetchSystemVersion();
  const { data: userInfo } = useFetchUserInfo();

  useEffect(() => {
    if (location.host !== Domain) {
      fetchSystemVersion();
    }
  }, [fetchSystemVersion]);

  function getItem(
    label: string,
    key: React.Key,
    icon?: React.ReactNode,
    children?: MenuItem[],
    type?: 'group',
  ): MenuItem {
    return {
      key,
      icon,
      children,
      label: t(label),
      type,
    } as MenuItem;
  }

  const items: MenuItem[] = useMemo(() => {
    return Object.values(UserSettingRouteKey)
      .filter((x) => {
        // 移除 file-management、knowledge-management、user-config 菜单项
        if (
          x === UserSettingRouteKey.FileManagement ||
          x === UserSettingRouteKey.KnowledgeManagement ||
          x === UserSettingRouteKey.UserConfig
        ) {
          return false;
        }
        if (x === UserSettingRouteKey.Management) {
          // 检查用户是否为超级管理员或全局管理员（包含 RBAC 权限）
          return userInfo?.is_superuser || userInfo?.is_admin;
        }
        return true;
      })
      .map((value) => getItem(value, value, UserSettingIconMap[value]));
  }, [userInfo?.is_superuser, userInfo?.is_admin]);

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === UserSettingRouteKey.Logout) {
      logout();
    } else {
      navigate(`/${UserSettingBaseKey}/${key}`);
    }
  };

  const selectedKeys = useMemo(() => {
    return [pathName];
  }, [pathName]);

  return (
    <section className={styles.sideBarWrapper}>
      <Menu
        selectedKeys={selectedKeys}
        mode="inline"
        items={items}
        onClick={handleMenuClick}
        style={{ width: 200 }}
      />
    </section>
  );
};

export default SideBar;
