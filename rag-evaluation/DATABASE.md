# 数据库设计文档

RAG 评估系统使用 SQLite 作为轻量级数据库解决方案，无需额外的数据库服务。

## 🏗️ 数据库架构

### 核心表结构

#### 1. `api_configs` - API 配置表
存储 LLM 提供商的 API 配置信息。

```sql
CREATE TABLE api_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    provider VARCHAR(50) NOT NULL,
    api_key VARCHAR(500) NOT NULL,
    endpoint VARCHAR(500),
    model VARCHAR(100),
    embedding_model VARCHAR(100),
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4000,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_default BOOLEAN DEFAULT 0
);
```

#### 2. `system_settings` - 系统设置表
存储系统级别的配置参数。

```sql
CREATE TABLE system_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key VARCHAR(100) NOT NULL UNIQUE,
    value TEXT,
    description TEXT,
    category VARCHAR(50) DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 3. `datasets` - 数据集表
存储评测数据集的元数据信息。

```sql
CREATE TABLE datasets (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    file_name VARCHAR(200),
    file_type VARCHAR(10),
    file_size INTEGER,
    storage_path VARCHAR(500),
    num_samples INTEGER DEFAULT 0,
    has_reference BOOLEAN DEFAULT 0,
    has_contexts BOOLEAN DEFAULT 0,
    sample_fields TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 4. `evaluation_tasks` - 评测任务表
存储评测任务的执行信息和状态。

```sql
CREATE TABLE evaluation_tasks (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200),
    chat_id VARCHAR(50) NOT NULL,
    dataset_id VARCHAR(50) NOT NULL,
    llm_model VARCHAR(100),
    embedding_model VARCHAR(100),
    metrics TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    total_samples INTEGER DEFAULT 0,
    processed_samples INTEGER DEFAULT 0,
    batch_size INTEGER DEFAULT 10,
    error_message TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);
```

#### 5. `evaluation_reports` - 评测报告表
存储评测结果和报告数据。

```sql
CREATE TABLE evaluation_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(50) NOT NULL UNIQUE,
    chat_id VARCHAR(50) NOT NULL,
    dataset_id VARCHAR(50) NOT NULL,
    overall_scores TEXT,
    detailed_scores TEXT,
    evaluation_metadata TEXT,
    report_file_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);
```

#### 6. `evaluation_logs` - 评测日志表
存储评测过程中的日志信息（用于调试）。

```sql
CREATE TABLE evaluation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(50),
    level VARCHAR(10),
    message TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES evaluation_tasks(id)
);
```

## 📊 数据关系

```
datasets (1) -----> (N) evaluation_tasks (1) -----> (1) evaluation_reports
```

- 一个数据集可以被多个评测任务使用
- 每个评测任务对应一个评测报告
- 评测日志与评测任务关联

## 🔧 使用方法

### 初始化数据库

```bash
cd backend
source venv/bin/activate
python init_db.py
```

### 数据库操作

#### 系统设置管理
```python
from db import get_config_manager

config_manager = get_config_manager()

# 读取设置
ragflow_url = config_manager.get_setting('ragflow_base_url')

# 更新设置
config_manager.update_setting('timeout', '300', 'Request timeout in seconds', 'api')
```

#### API 配置管理
```python
from db import get_config_manager

config_manager = get_config_manager()

# 创建 API 配置
config_id = config_manager.create_api_config({
    'name': 'SiliconFlow',
    'provider': 'siliconflow',
    'api_key': 'sk-your-key',
    'model': 'Qwen/Qwen2.5-32B-Instruct',
    'embedding_model': 'BAAI/bge-m3'
})

# 获取默认配置
default_config = config_manager.get_default_api_config()
```

#### 数据集管理
```python
from db import get_dataset_manager

dataset_manager = get_dataset_manager()

# 创建数据集
dataset_id = dataset_manager.create_dataset({
    'id': 'unique-dataset-id',
    'name': 'Test Dataset',
    'description': 'Test dataset',
    'num_samples': 100,
    'has_reference': True,
    'has_contexts': True
})

# 获取数据集列表
datasets = dataset_manager.get_datasets(limit=20, offset=0)
```

#### 任务管理
```python
from db import get_task_manager

task_manager = get_task_manager()

# 创建任务
task_id = task_manager.create_task({
    'id': 'unique-task-id',
    'name': 'Evaluation Task',
    'chat_id': 'chat-assistant-id',
    'dataset_id': 'dataset-id',
    'metrics': ['answer_relevancy', 'context_precision']
})

# 更新任务状态
task_manager.update_task_status(task_id, 'running', progress=50)
```

#### 报告管理
```python
from db import get_report_manager

report_manager = get_report_manager()

# 保存报告
report_id = report_manager.save_report({
    'task_id': 'task-id',
    'chat_id': 'chat-id',
    'dataset_id': 'dataset-id',
    'overall_scores': {'answer_relevancy': {'mean': 0.8}},
    'detailed_scores': [{'answer_relevancy': 0.8}],
    'evaluation_metadata': {'llm_model': 'gpt-4'}
})

# 获取报告
report = report_manager.get_report('task-id')
```

## 🗂️ 文件存储

### 数据文件结构
```
backend/
├── evaluation.db              # SQLite 数据库文件
├── tmp/
│   ├── datasets/              # 数据集文件存储
│   │   ├── {dataset_id}.json
│   │   └── {dataset_id}.csv
│   └── evaluation/
│       └── reports/           # 评测报告文件
│           └── {task_id}.json
└── logs/                      # 应用日志
    └── evaluation.log
```

## 🔍 查询示例

### 查询最近的评测任务
```sql
SELECT t.*, d.name as dataset_name
FROM evaluation_tasks t
JOIN datasets d ON t.dataset_id = d.id
ORDER BY t.created_at DESC
LIMIT 10;
```

### 查询系统配置统计
```sql
SELECT category, COUNT(*) as setting_count
FROM system_settings
GROUP BY category;
```

### 查询评测任务成功率
```sql
SELECT
    status,
    COUNT(*) as task_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM evaluation_tasks), 2) as percentage
FROM evaluation_tasks
GROUP BY status;
```

## 🚀 性能优化

### 索引
数据库已创建以下索引以提高查询性能：
- `idx_datasets_name` - 数据集名称索引
- `idx_tasks_status` - 任务状态索引
- `idx_tasks_created_at` - 任务创建时间索引
- `idx_reports_task_id` - 报告任务ID索引
- `idx_settings_category` - 设置类别索引

### 定期维护
```sql
-- 清理旧的日志记录
DELETE FROM evaluation_logs
WHERE created_at < datetime('now', '-30 days');

-- 优化数据库
VACUUM;

-- 重建索引
REINDEX;
```

## 🔄 备份与恢复

### 备份
```bash
# 备份数据库
cp evaluation.db backup/evaluation_$(date +%Y%m%d_%H%M%S).db

# 备份数据文件
tar -czf backup/data_$(date +%Y%m%d_%H%M%S).tar.gz tmp/datasets tmp/evaluation
```

### 恢复
```bash
# 恢复数据库
cp backup/evaluation_20241201_120000.db evaluation.db

# 恢复数据文件
tar -xzf backup/data_20241201_120000.tar.gz
```

## 🛠️ 开发调试

### 查看数据库内容
```bash
# 使用 sqlite3 命令行工具
sqlite3 evaluation.db

# 查看表结构
.schema

# 查看所有表
.tables

# 查询数据
SELECT * FROM datasets LIMIT 5;
```

### 测试数据库功能
```bash
# 运行数据库测试
python test_db.py
```

## 📝 注意事项

1. **并发访问**: SQLite 写操作会锁定整个数据库，适合中小型应用
2. **文件权限**: 确保应用对数据库文件和目录有读写权限
3. **备份策略**: 定期备份 `evaluation.db` 文件
4. **存储空间**: 监控 `tmp/` 目录大小，定期清理旧文件
5. **数据迁移**: 如需更换数据库系统，可导出 SQL 脚本进行迁移