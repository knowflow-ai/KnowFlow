# SiliconFlow API 配置指南

## 如何在评测系统中配置 SiliconFlow

### 1. 进入系统设置
访问评测系统 → 系统设置 → API 配置

### 2. 填写配置信息

#### 基本配置
- **LLM 提供商**: 选择 "SiliconFlow（硅基流动）"
- **模型**: 可以选择或手动输入，例如：
  - `Qwen/QwQ-32B` - 通义千问推理模型
  - `Qwen/Qwen2.5-72B-Instruct` - 通义千问2.5
  - `Qwen/Qwen3-8B` - 通义千问3代 8B 模型（轻量高效）
  - `deepseek-ai/DeepSeek-V3` - DeepSeek V3
  - 或直接输入其他模型名称

- **API 密钥**: 你的 SiliconFlow API Token
  ```
  格式: sk-xxxxxxxxxxxxxxxxxxxxxxxx
  ```

- **API 端点**:
  ```
  https://api.siliconflow.cn/v1
  ```

#### 高级配置（可选）
- **温度参数**: 0-1 之间，推荐 0（确定性输出）
- **最大 Token 数**: 根据任务需求调整，推荐 2000-4000

### 3. 测试配置

点击 "测试连接" 按钮，系统会：
1. 验证 API Key 是否有效
2. 向 SiliconFlow 发送测试请求
3. 返回测试结果

**成功示例**:
```
✓ 连接测试成功
```

**失败示例**:
```
✗ 连接测试失败: Invalid API Key
```

### 4. 保存配置

测试成功后，点击 "保存配置" 按钮。

## 配置示例

### SiliconFlow Qwen/QwQ-32B
```
Provider: SiliconFlow（硅基流动）
Model: Qwen/QwQ-32B
API Key: sk-your-token-here
Endpoint: https://api.siliconflow.cn/v1
Temperature: 0
Max Tokens: 2000
```

### 其他国内服务商

#### 智谱 AI (ChatGLM)
```
Provider: 智谱 AI
Model: glm-4
API Key: your-zhipu-api-key
Endpoint: https://open.bigmodel.cn/api/paas/v4
```

#### 月之暗面 (Kimi)
```
Provider: 月之暗面（Kimi）
Model: moonshot-v1-8k
API Key: your-moonshot-api-key
Endpoint: https://api.moonshot.cn/v1
```

## 注意事项

1. **API Key 安全**: 请妥善保管你的 API Key，不要泄露给他人
2. **Token 限制**: 注意查看服务商的 Token 限制和费率
3. **模型可用性**: 确保选择的模型在你的账户中可用
4. **网络连接**: 确保服务器可以访问 API 端点

## 故障排查

### 连接失败
- 检查 API Key 是否正确
- 验证 API 端点地址是否正确
- 确认网络可以访问 SiliconFlow 服务

### 模型不存在
- 确认模型名称拼写正确
- 检查模型是否在你的账户中可用
- 尝试使用其他可用模型

### 超时错误
- 检查网络连接
- 增加超时时间配置
- 尝试切换到其他模型

## 获取 API Key

访问 SiliconFlow 官网: https://siliconflow.cn
1. 注册账号
2. 进入控制台
3. 创建 API Key
4. 复制并粘贴到评测系统

## 支持的模型列表

### 大语言模型
- Qwen/QwQ-32B - 推理优化模型（32B 参数，适合复杂推理任务）
- Qwen/Qwen2.5-72B-Instruct - 高性能对话模型（72B 参数）
- Qwen/Qwen3-8B - 轻量高效模型（8B 参数，快速响应）
- deepseek-ai/DeepSeek-V3 - DeepSeek 最新版本
- 01-ai/Yi-1.5-34B-Chat - 零一万物对话模型

### 更多模型
访问 SiliconFlow 文档查看完整的模型列表和定价信息。
