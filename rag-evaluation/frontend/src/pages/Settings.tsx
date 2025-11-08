import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Select,
  Switch,
  Button,
  InputNumber,
  Typography,
  Divider,
  Space,
  Alert,
  Modal,
  message,
  Tabs,
  Row,
  Col,
  Tooltip,
  App,
} from 'antd';
import {
  SaveOutlined,
  ReloadOutlined,
  ApiOutlined,
  SettingOutlined,
  KeyOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { systemApi } from '../services/evaluation';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;
const { TextArea } = Input;
const { TabPane } = Tabs;

interface APIConfig {
  provider: string;
  apiKey: string;
  endpoint?: string;
  model: string;
  embeddingModel?: string;
  temperature: number;
  maxTokens: number;
}

const Settings: React.FC = () => {
  const { modal } = App.useApp();
  const [form] = Form.useForm();
  const [apiForm] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [isAutoSaving, setIsAutoSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(true);

  const [apiConfig, setApiConfig] = useState<APIConfig>({
    provider: 'openai',
    apiKey: '',
    model: 'gpt-4',
    temperature: 0,
    maxTokens: 2000,
  });

  
  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const config = await systemApi.getConfig();
      console.log('Fetched config:', config);

      if (config.api) {
        setApiConfig(config.api);

        // 处理 model 字段：转换为数组以适配 Select mode="tags"
        const apiConfigForForm = {
          ...config.api,
          model: config.api.model ? [config.api.model] : ['gpt-4']
        };

        apiForm.setFieldsValue(apiConfigForForm);
        console.log('Set API form values:', apiConfigForForm);
      }
    } catch (error) {
      console.error('Failed to fetch config:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async (values: any) => {
    setSaving(true);
    try {
      // 包装配置数据，区分是哪个表单提交的
      let configData;

      // 如果有 provider 字段，说明是 API 配置表单
      if ('provider' in values) {
        // 处理 model 字段：如果是数组（tags mode），取第一个值
        let modelValue = values.model;
        if (Array.isArray(modelValue)) {
          modelValue = modelValue[0] || 'gpt-4';
        }

        configData = {
          api_config: {
            ...values,
            model: modelValue
          }
        };
      }
      // 否则是常规设置表单
      else {
        configData = values;
      }

      console.log('Saving config:', configData);
      await systemApi.updateConfig(configData);
      message.success('配置保存成功');
      await fetchConfig();
    } catch (error) {
      console.error('Failed to save settings:', error);
      message.error('配置保存失败');
    } finally {
      setSaving(false);
    }
  };

  
  // Provider 对应的默认 endpoint
  const providerEndpoints: Record<string, string> = {
    'siliconflow': 'https://api.siliconflow.cn/v1',
    'deepseek': 'https://api.deepseek.com/v1',
    'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
    'moonshot': 'https://api.moonshot.cn/v1',
  };

  // 处理 provider 变化
  const handleProviderChange = (value: string) => {
    const defaultEndpoint = providerEndpoints[value];
    if (defaultEndpoint) {
      apiForm.setFieldsValue({ endpoint: defaultEndpoint });
      message.info(`已自动填充 ${value} 的默认 API 端点`);
    } else {
      apiForm.setFieldsValue({ endpoint: '' });
    }
  };

  // 自动保存 API 配置
  const autoSaveApiKey = async () => {
    setIsAutoSaving(true);
    try {
      const values = apiForm.getFieldsValue();
      
      // 处理 model 字段
      let modelValue = values.model;
      if (Array.isArray(modelValue)) {
        modelValue = modelValue[0] || 'gpt-4';
      }

      const configData = {
        api_config: {
          ...values,
          model: modelValue
        }
      };

      await systemApi.updateConfig(configData);
      setIsSaved(true);
      message.success('已自动保存', 1);
    } catch (error: any) {
      console.error('Auto save failed:', error);
      message.error('自动保存失败');
    } finally {
      setIsAutoSaving(false);
    }
  };

  // 任意字段失去焦点时自动保存
  const handleFieldBlur = () => {
    const values = apiForm.getFieldsValue();
    // 至少要有 API Key 才保存
    if (values.apiKey && values.apiKey.trim()) {
      autoSaveApiKey();
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    try {
      // 获取当前表单的值
      const values = apiForm.getFieldsValue();

      if (!values.apiKey) {
        message.warning('请先输入 API Key');
        setTestingConnection(false);
        return;
      }

      // 处理 model 字段：如果是数组（tags mode），取第一个值
      let modelValue = values.model;
      if (Array.isArray(modelValue)) {
        modelValue = modelValue[0] || 'gpt-4';
      }

      console.log('Testing connection with config:', {
        provider: values.provider,
        apiKey: values.apiKey?.substring(0, 10) + '...',
        endpoint: values.endpoint,
        model: modelValue,
      });

      // 调用测试连接API
      const result = await systemApi.testConnection({
        provider: values.provider || 'openai',
        apiKey: values.apiKey,
        endpoint: values.endpoint,
        model: modelValue || 'gpt-4',
      });

      if (result.success) {
        modal.success({
          title: '连接测试成功',
          content: result.message || 'API 连接正常，可以开始使用',
        });
      } else {
        modal.error({
          title: '连接测试失败',
          content: result.message || '请检查 API 配置是否正确',
        });
      }
    } catch (error: any) {
      console.error('Failed to test connection:', error);
      modal.error({
        title: '连接测试失败',
        content: error?.response?.data?.message || '请检查网络连接和 API 配置',
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleResetSettings = () => {
    Modal.confirm({
      title: '重置设置',
      content: '确定要重置所有设置为默认值吗？',
      onOk: () => {
        form.resetFields();
        message.info('设置已重置为默认值');
      },
    });
  };

  
  return (
    <div>
      <Title level={2}>系统设置</Title>

      <Tabs defaultActiveKey="general" style={{ marginTop: 24 }}>
        <TabPane
          tab={
            <span>
              <SettingOutlined />
              常规设置
            </span>
          }
          key="general"
        >
          <Card>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSaveSettings}
              initialValues={{
                systemName: 'KnowFlow Evaluation',
                language: 'zh-CN',
                timezone: 'Asia/Shanghai',
                batchSize: 10,
                maxWorkers: 4,
                timeout: 30,
                autoRetry: true,
                retryCount: 3,
              }}
            >
              <Title level={4}>基础配置</Title>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="系统名称"
                    name="systemName"
                    rules={[{ required: true }]}
                  >
                    <Input placeholder="评测系统名称" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="系统语言"
                    name="language"
                    rules={[{ required: true }]}
                  >
                    <Select>
                      <Option value="zh-CN">简体中文</Option>
                      <Option value="en-US">English</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Divider />

              <Title level={4}>评测配置</Title>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item
                    label="批处理大小"
                    name="batchSize"
                    tooltip="每批处理的样本数量"
                  >
                    <InputNumber min={1} max={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    label="并发数"
                    name="maxWorkers"
                    tooltip="同时运行的工作线程数"
                  >
                    <InputNumber min={1} max={10} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    label="超时时间（秒）"
                    name="timeout"
                    tooltip="单个请求的最大等待时间"
                  >
                    <InputNumber min={10} max={300} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="自动重试"
                    name="autoRetry"
                    valuePropName="checked"
                  >
                    <Switch checkedChildren="开启" unCheckedChildren="关闭" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="重试次数"
                    name="retryCount"
                  >
                    <InputNumber min={1} max={5} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={loading}>
                    保存设置
                  </Button>
                  <Button icon={<ReloadOutlined />} onClick={handleResetSettings}>
                    重置默认
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>

        <TabPane
          tab={
            <span>
              <ApiOutlined />
              API 配置
            </span>
          }
          key="api"
        >
          <Card>
            <Form
              form={apiForm}
              layout="vertical"
              onFinish={handleSaveSettings}
              initialValues={{
                ...apiConfig,
                model: apiConfig.model ? [apiConfig.model] : ['gpt-4']
              }}
            >
              <Alert
                message="API 密钥安全提示"
                description="请确保 API 密钥安全，不要在公开场合分享。系统会自动加密存储您的密钥。"
                type="warning"
                showIcon
                style={{ marginBottom: 24 }}
              />

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="LLM 提供商"
                    name="provider"
                    rules={[{ required: true }]}
                  >
                    <Select 
                      onChange={handleProviderChange}
                      onBlur={handleFieldBlur}
                    >
                      <Option value="openai">OpenAI</Option>
                      <Option value="anthropic">Anthropic</Option>
                      <Option value="azure">Azure OpenAI</Option>
                      <Option value="siliconflow">SiliconFlow（硅基流动）</Option>
                      <Option value="zhipu">智谱 AI</Option>
                      <Option value="moonshot">月之暗面（Kimi）</Option>
                      <Option value="deepseek">DeepSeek</Option>
                      <Option value="custom">自定义</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="模型"
                    name="model"
                    rules={[{ required: true }]}
                    tooltip="可以手动输入模型名称，如 Qwen/QwQ-32B"
                  >
                    <Select
                      mode="tags"
                      maxCount={1}
                      placeholder="选择或输入模型名称"
                      onBlur={handleFieldBlur}
                    >
                      <Option value="gpt-4">GPT-4</Option>
                      <Option value="gpt-4-turbo">GPT-4 Turbo</Option>
                      <Option value="gpt-3.5-turbo">GPT-3.5 Turbo</Option>
                      <Option value="claude-3-opus">Claude 3 Opus</Option>
                      <Option value="claude-3-sonnet">Claude 3 Sonnet</Option>
                      <Option value="Qwen/QwQ-32B">Qwen/QwQ-32B (SiliconFlow)</Option>
                      <Option value="Qwen/Qwen2.5-72B-Instruct">Qwen2.5-72B (SiliconFlow)</Option>
                      <Option value="Qwen/Qwen3-8B">Qwen/Qwen3-8B (SiliconFlow)</Option>
                      <Option value="deepseek-chat">DeepSeek-V3</Option>
                      <Option value="glm-4">GLM-4 (智谱)</Option>
                      <Option value="moonshot-v1-8k">Moonshot-v1-8k</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                label="API 密钥"
                name="apiKey"
                rules={[{ required: true }]}
              >
                <Input.Password
                  placeholder="输入您的 API 密钥"
                  prefix={<KeyOutlined />}
                  onBlur={handleFieldBlur}
                  onChange={() => setIsSaved(false)}
                />
              </Form.Item>

              <Form.Item
                label="API 端点"
                name="endpoint"
                tooltip="留空则使用默认端点。SiliconFlow: https://api.siliconflow.cn/v1"
              >
                <Input 
                  placeholder="https://api.siliconflow.cn/v1"
                  onBlur={handleFieldBlur}
                />
              </Form.Item>

              <Form.Item
                label="Embedding 模型"
                name="embeddingModel"
                tooltip="用于计算语义相似度的向量模型。某些评测指标（如 AnswerCorrectness）需要此模型"
              >
                <Select
                  mode="tags"
                  maxCount={1}
                  placeholder="选择或输入 Embedding 模型名称"
                  allowClear
                  onBlur={handleFieldBlur}
                >
                  <Option value="BAAI/bge-large-zh-v1.5">BAAI/bge-large-zh-v1.5 (SiliconFlow)</Option>
                  <Option value="BAAI/bge-m3">BAAI/bge-m3 (SiliconFlow)</Option>
                  <Option value="text-embedding-3-small">text-embedding-3-small (OpenAI)</Option>
                  <Option value="text-embedding-3-large">text-embedding-3-large (OpenAI)</Option>
                  <Option value="text-embedding-ada-002">text-embedding-ada-002 (OpenAI)</Option>
                </Select>
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="温度参数"
                    name="temperature"
                    tooltip="控制输出的随机性，0 表示确定性输出"
                  >
                    <InputNumber 
                      min={0} 
                      max={1} 
                      step={0.1} 
                      style={{ width: '100%' }}
                      onBlur={handleFieldBlur}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="最大 Token 数"
                    name="maxTokens"
                  >
                    <InputNumber 
                      min={100} 
                      max={8000} 
                      style={{ width: '100%' }}
                      onBlur={handleFieldBlur}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item>
                <Button
                  type="primary"
                  icon={<ApiOutlined />}
                  onClick={handleTestConnection}
                  loading={testingConnection}
                >
                  测试连接
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>

        </Tabs>
    </div>
  );
};

export default Settings;