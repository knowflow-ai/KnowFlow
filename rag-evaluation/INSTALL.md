# 安装指南

## 环境要求

- **Python**: 3.8 - 3.12 (推荐 3.11)
- **Node.js**: >= 16.0.0
- **操作系统**: Linux, macOS, Windows

## Python 3.13 兼容性问题

由于 pandas 2.1.4 与 Python 3.13 存在编译兼容性问题，推荐使用以下解决方案：

### 方案1：使用 Python 3.11 (推荐)

```bash
# 安装 pyenv 管理多 Python 版本
brew install pyenv  # macOS
# 或使用系统包管理器安装

# 安装 Python 3.11
pyenv install 3.11.9
pyenv local 3.11.9

# 验证版本
python --version  # 应该显示 Python 3.11.9
```

### 方案2：使用预编译包

如果必须使用 Python 3.13，可以使用预编译的 pandas 包：

```bash
pip install pandas --only-binary=all
```

### 方案3：使用 conda

```bash
conda create -n rag-eval python=3.11
conda activate rag-eval
pip install -r requirements-minimal.txt
```

## 标准安装流程

### 1. 克隆项目
```bash
cd /Users/zxwei/zhishi/knowflow/rag-evaluation
```

### 2. 后端安装
```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements-minimal.txt
```

### 3. 前端安装
```bash
cd ../frontend

# 安装依赖
npm install
# 或 yarn install
```

### 4. 配置环境变量
```bash
# 后端配置
cp ../.env.example backend/.env
# 编辑 backend/.env 文件

# 前端配置
cp frontend/.env.example frontend/.env
# 编辑 frontend/.env 文件
```

## 快速启动

### 使用启动脚本
```bash
# 安装依赖并启动
./start.sh dev

# 仅安装依赖
./start.sh install

# 仅启动后端
./start.sh backend

# 仅启动前端
./start.sh frontend
```

### 手动启动
```bash
# 启动后端
cd backend
source venv/bin/activate
python app_new.py

# 启动前端 (新终端)
cd frontend
npm run dev
```

## 常见问题

### Q: pandas 编译失败
A: 使用 `requirements-minimal.txt` 或安装 Python 3.11

### Q: RAGAS 安装失败
A: 确保安装了所有依赖：`pip install ragas langchain langchain-openai`

### Q: 前端代理错误
A: 检查 `frontend/vite.config.ts` 中的代理配置

### Q: 端口冲突
A: 修改配置文件中的 PORT 和前端配置中的端口

## 验证安装

```bash
# 运行测试脚本
./test.sh

# 手动测试后端
curl http://localhost:5002/health

# 手动测试前端
curl http://localhost:3001
```