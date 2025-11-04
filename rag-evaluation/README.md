# RAG 评估系统

独立部署的 RAG (Retrieval-Augmented Generation) 系统评测工具，基于 RAGAS 框架构建。

## 🚀 特性

- **多系统支持**: 可与 RAGFlow、LangChain 等多种 RAG 系统集成
- **丰富指标**: 基于 RAGAS 框架的多种评测指标
- **可视化报告**: 直观的评测结果展示
- **批量评测**: 支持大规模数据集评测
- **实时监控**: 实时查看评测进度和结果

## 📋 评测指标

### LLM 基础指标
- **忠实度 (Faithfulness)**: 评估回答是否基于提供的上下文
- **答案相关性 (Answer Relevancy)**: 评估答案与问题的相关程度
- **上下文精确度 (Context Precision)**: 评估检索到的上下文与问题的相关性
- **上下文召回率 (Context Recall)**: 评估是否检索到回答问题所需的所有相关信息

### 传统指标
- **答案相似度 (Answer Similarity)**: 基于向量相似度的答案评估
- **响应时间 (Response Time)**: 系统响应速度评测
- **Token 使用量**: 计算资源消耗评估

## 🏗️ 系统架构

```
rag-evaluation/
├── backend/                 # 后端服务
│   ├── app.py              # Flask 应用入口
│   ├── config.py           # 配置文件
│   ├── evaluation.py       # 评测 API 路由
│   ├── services/           # 业务逻辑层
│   │   └── evaluation/     # 评测服务
│   └── requirements.txt    # Python 依赖
├── frontend/               # 前端界面
│   ├── src/
│   │   ├── components/     # React 组件
│   │   ├── pages/          # 页面组件
│   │   └── services/       # API 服务
│   ├── package.json        # Node.js 依赖
│   └── vite.config.ts      # Vite 配置
└── README.md              # 项目文档
```

## 🛠️ 安装部署

### 后端部署

1. **环境准备**
```bash
# 克隆项目
cd rag-evaluation/backend

# 推荐：使用 Python 3.11 (与 pandas 兼容性最好)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 升级 pip
pip install --upgrade pip

# 安装依赖 (使用最小依赖避免编译问题)
pip install -r requirements-minimal.txt
```

2. **配置环境变量**
```bash
# 复制环境变量模板
cp ../.env.example .env

# 编辑配置文件
vim .env
```

3. **启动服务**
```bash
# 开发环境
python app_new.py

# 生产环境
gunicorn -w 4 -b 0.0.0.0:5002 app_new:app
```

### 前端部署

1. **环境准备**
```bash
cd rag-evaluation/frontend

# 安装依赖
npm install
# 或 yarn install
```

2. **配置环境变量**
```bash
# 复制环境变量模板
cp .env.example .env

# 根据需要修改配置
```

3. **启动服务**
```bash
# 开发环境
npm run dev

# 构建生产版本
npm run build
```

## 📊 使用指南

### 1. 创建数据集

支持的文件格式：
- JSON (推荐)
- CSV
- Excel (.xlsx, .xls)

JSON 格式示例：
```json
[
  {
    "question": "什么是人工智能？",
    "expected_answer": "人工智能是计算机科学的一个分支...",
    "contexts": ["上下文信息1", "上下文信息2"],
    "reference_contexts": ["参考上下文1", "参考上下文2"]
  }
]
```

### 2. 配置对话助手

系统支持从 RAGFlow 获取对话助手列表，确保：
- RAGFlow 服务正在运行
- 配置了正确的 RAGFLOW_API_KEY

### 3. 运行评测

1. 选择要评测的对话助手
2. 选择评测数据集
3. 选择评测指标
4. 配置评测参数
5. 启动评测任务

### 4. 查看报告

评测完成后，可以查看：
- 总体评分
- 详细分数分布
- 单个样本结果
- 可视化图表

## 🔧 配置说明

### 后端配置

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `PORT` | 服务端口 | 5002 |
| `RAGFLOW_BASE_URL` | RAGFlow 服务地址 | http://localhost:9380 |
| `RAGFLOW_API_KEY` | RAGFlow API 密钥 | - |
| `OPENAI_API_KEY` | OpenAI API 密钥 | - |
| `SILICONFLOW_API_KEY` | 硅基流动 API 密钥 | - |
| `DEFAULT_LLM_MODEL` | 默认 LLM 模型 | Qwen/Qwen2.5-32B-Instruct |

### 前端配置

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `VITE_API_BASE_URL` | 后端 API 地址 | http://localhost:5002/api/v1 |
| `VITE_RAGFLOW_API_URL` | RAGFlow API 地址 | http://localhost:9380/api/v1 |

## 🚀 快速开始

### 方法一：自动安装 (推荐)
```bash
cd rag-evaluation
./install.sh  # 自动安装所有依赖

# 启动系统
./start.sh dev
```

### 方法二：手动安装

1. **环境准备**
```bash
cd rag-evaluation/backend

# 推荐使用 Python 3.10
python3.10 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

2. **启动后端服务**
```bash
cd rag-evaluation/backend
source venv/bin/activate
python app_new.py
```

3. **启动前端服务**
```bash
cd rag-evaluation/frontend
npm run dev
```

4. **访问系统**
- 前端界面: http://localhost:3001
- 后端 API: http://localhost:5002
- API 文档: http://localhost:5002/api/v1/evaluation/docs

### ⚠️ Python 版本说明
- **推荐**: Python 3.10 (兼容性最佳，无编译问题)
- **支持**: Python 3.8 - 3.12
- **问题**: Python 3.13 存在较多兼容性问题

强烈建议使用 Python 3.10：
```bash
# 使用 pyenv 安装和管理 Python 版本
brew install pyenv
pyenv install 3.10.14
pyenv local 3.10.14
```

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目基于 MIT 许可证开源 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 支持

如果您遇到问题或有建议，请：
1. 查看 [常见问题](docs/FAQ.md)
2. 提交 [Issue](https://github.com/your-repo/rag-evaluation/issues)
3. 联系维护者

## 🎯 路线图

- [ ] 支持更多 RAG 系统
- [ ] 添加更多评测指标
- [ ] 支持自定义评测模板
- [ ] 增加团队协作功能
- [ ] 支持评测结果对比
- [ ] 添加性能基准测试