import { useTranslate } from '@/hooks/common-hooks';
import { MenuProps } from 'antd';
import React from 'react';
import User from '../user';

import { useTheme } from '@/components/theme-provider';
import { LanguageList, LanguageMap } from '@/constants/common';
import { useChangeLanguage } from '@/hooks/logic-hooks';
import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import styled from './index.less';

const Circle = ({ children, ...restProps }: React.PropsWithChildren) => {
  return (
    <div {...restProps} className={styled.circle}>
      {children}
    </div>
  );
};

const handleGithubCLick = () => {
  // window.open('https://github.com/infiniflow/ragflow', 'target');
  window.open('https://github.com/weizxfree/KnowFlow', 'target');
};

const handleDocHelpCLick = () => {
  // window.open('https://ragflow.io/docs/dev/category/guides', 'target');
  window.open(
    'https://www.knowflowchat.cn/site/docs/what-is-docsearch/',
    'target',
  );
};

const RightToolBar = () => {
  const { t } = useTranslate('common');
  const changeLanguage = useChangeLanguage();
  const { setTheme, theme } = useTheme();

  const {
    data: { language = 'English' },
  } = useFetchUserInfo();

  const handleItemClick: MenuProps['onClick'] = ({ key }) => {
    changeLanguage(key);
  };

  const items: MenuProps['items'] = LanguageList.map((x) => ({
    key: x,
    label: <span>{LanguageMap[x as keyof typeof LanguageMap]}</span>,
  })).reduce<MenuProps['items']>((pre, cur) => {
    return [...pre!, { type: 'divider' }, cur];
  }, []);

  const onMoonClick = React.useCallback(() => {
    setTheme('light');
  }, [setTheme]);
  const onSunClick = React.useCallback(() => {
    setTheme('dark');
  }, [setTheme]);

  return (
    <div className={styled.toolbarWrapper}>
      <User></User>
    </div>
  );
};

export default RightToolBar;
