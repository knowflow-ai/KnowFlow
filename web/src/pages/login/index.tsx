import { useLogin, useRegister, useSystemConfig } from '@/hooks/login-hooks';
import { rsaPsw } from '@/utils';
import { Button, Form, Input } from 'antd';
import { useEffect, useState } from 'react';
import { Icon, useNavigate } from 'umi';
// import RightPanel from './right-panel';

import { Domain } from '@/constants/common';
import styles from './index.less';

const Login = () => {
  const [title, setTitle] = useState('login');
  const navigate = useNavigate();
  const { login, loading: signLoading } = useLogin();
  const { register, loading: registerLoading } = useRegister();
  const { data: systemConfig } = useSystemConfig();
  // const { t } = useTranslation('translation', { keyPrefix: 'login' });
  const loading = signLoading || registerLoading;

  // 获取注册是否启用的配置
  const isRegisterEnabled = systemConfig?.registerEnabled === 1;

  const changeTitle = () => {
    if (isRegisterEnabled) {
      setTitle((title) => (title === 'login' ? 'register' : 'login'));
    }
  };
  const [form] = Form.useForm();

  useEffect(() => {
    form.validateFields(['nickname']);
  }, [form]);

  // 如果注册被禁用且当前在注册页面，自动切换到登录页面
  useEffect(() => {
    if (!isRegisterEnabled && title === 'register') {
      setTitle('login');
    }
  }, [isRegisterEnabled, title]);

  const onCheck = async () => {
    try {
      const params = await form.validateFields();

      const rsaPassWord = rsaPsw(params.password) as string;

      if (title === 'login') {
        const code = await login({
          email: `${params.email}`.trim(),
          password: rsaPassWord,
        });
        if (code === 0) {
          navigate('/knowledge');
        }
      } else {
        const code = await register({
          nickname: params.nickname,
          email: params.email,
          password: rsaPassWord,
        });
        if (code === 0) {
          setTitle('login');
        }
      }
    } catch (errorInfo) {
      console.log('Failed:', errorInfo);
    }
  };
  const formItemLayout = {
    labelCol: { span: 6 },
    // wrapperCol: { span: 8 },
  };

  const toGoogle = () => {
    window.location.href =
      'https://github.com/login/oauth/authorize?scope=user:email&client_id=302129228f0d96055bee';
  };

  return (
    <div className={styles.loginPage}>
      <div className={styles.loginLeft}>
        <div className={styles.leftContainer}>
          <div className={styles.loginTitle}>
            <div className={styles.loginLogo}>
              <div className={styles.logo}></div>
              <div className={styles.name}>KnowFlow</div>
            </div>
          </div>

          <Form
            form={form}
            layout="vertical"
            name="dynamic_rule"
            style={{ maxWidth: 600 }}
          >
            <Form.Item
              {...formItemLayout}
              name="email"
              // label={t('emailLabel')}
              rules={[{ required: true, message: '请输入邮箱地址' }]}
            >
              <Input size="large" placeholder="请输入邮箱地址" />
            </Form.Item>
            {title === 'register' && (
              <Form.Item
                {...formItemLayout}
                name="nickname"
                // label={t('nicknameLabel')}
                rules={[{ required: true, message: '请输入昵称' }]}
              >
                <Input size="large" placeholder="请输入昵称" />
              </Form.Item>
            )}
            <Form.Item
              {...formItemLayout}
              name="password"
              // label={t('passwordLabel')}
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                size="large"
                placeholder="请输入密码"
                onPressEnter={onCheck}
              />
            </Form.Item>
            {/* {title === 'login' && (
              <Form.Item name="remember" valuePropName="checked">
                <Checkbox> 记住我</Checkbox>
              </Form.Item>
            )} */}
            <div>
              {title === 'login' && isRegisterEnabled && (
                <div>
                  {'没有账号?'}
                  <Button type="link" onClick={changeTitle}>
                    {'注册'}
                  </Button>
                </div>
              )}
              {title === 'register' && isRegisterEnabled && (
                <div>
                  {'已有账号?'}
                  <Button type="link" onClick={changeTitle}>
                    {'去登录'}
                  </Button>
                </div>
              )}
            </div>
            <Button
              type="primary"
              block
              size="large"
              onClick={onCheck}
              loading={loading}
            >
              {title === 'login' ? '登录' : '注册'}
            </Button>
            {title === 'login' && (
              <>
                {/* <Button
                  block
                  size="large"
                  onClick={toGoogle}
                  style={{ marginTop: 15 }}
                >
                  <div>
                    <Icon
                      icon="local:google"
                      style={{ verticalAlign: 'middle', marginRight: 5 }}
                    />
                    Sign in with Google
                  </div>
                </Button> */}
                {location.host === Domain && (
                  <Button
                    block
                    size="large"
                    onClick={toGoogle}
                    style={{ marginTop: 15 }}
                  >
                    <div className="flex items-center">
                      <Icon
                        icon="local:github"
                        style={{ verticalAlign: 'middle', marginRight: 5 }}
                      />
                      Sign in with Github
                    </div>
                  </Button>
                )}
              </>
            )}
          </Form>
        </div>
      </div>
      {/* <div className={styles.loginRight}>
        <RightPanel></RightPanel>
      </div> */}
    </div>
  );
};

export default Login;
