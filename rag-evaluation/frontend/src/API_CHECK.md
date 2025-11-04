# KnowFlow 评测系统 API 接口检查清单

## 当前接口状态（2025-11-03 更新）

### 1. 知识库相关 API ✅
- `GET /api/v1/knowledgebases` - 获取知识库列表
  - 状态: 已实现并测试
  - 前端调用: Tasks.tsx ✅ 已集成

### 2. 评测数据集 API ✅
- `GET /api/v1/evaluation/datasets` - 获取数据集列表
  - 状态: 已实现并集成
  - 前端调用: Datasets.tsx ✅ 已集成

- `POST /api/v1/evaluation/datasets` - 上传数据集
  - 状态: 已实现并集成
  - 前端调用: Datasets.tsx ✅ 已集成

- `GET /api/v1/evaluation/datasets/{id}` - 获取数据集详情
  - 状态: 已实现
  - 前端调用: Datasets.tsx ✅ 已集成（预览功能）

- `GET /api/v1/evaluation/datasets/{id}/samples` - 获取数据集样本
  - 状态: 已实现并集成
  - 前端调用: Datasets.tsx ✅ 已集成（预览功能）

- `DELETE /api/v1/evaluation/datasets/{id}` - 删除数据集
  - 状态: 已实现并集成
  - 前端调用: Datasets.tsx ✅ 已集成

### 3. 评测任务 API ⚠️
- `GET /api/v1/evaluation/tasks` - 获取任务列表
  - 状态: 已实现（返回空数据）
  - 前端调用: Tasks.tsx, Dashboard.tsx ✅ 已集成

- `POST /api/v1/evaluation/tasks` - 创建评测任务
  - 状态: 已实现
  - 前端调用: Tasks.tsx

- `GET /api/v1/evaluation/tasks/{id}` - 获取任务状态
  - 状态: 已实现（返回示例数据）
  - 前端调用: Tasks.tsx

### 4. 评测报告 API ⚠️
- `GET /api/v1/evaluation/reports` - 获取报告列表
  - 状态: 已实现（返回空数组）
  - 前端调用: Reports.tsx ✅ 已集成

- `GET /api/v1/evaluation/reports/{task_id}` - 获取评测报告
  - 状态: 已实现（返回示例数据）
  - 前端调用: Reports.tsx

### 5. 指标管理 API ⚠️
- `GET /api/v1/evaluation/metrics` - 获取可用指标
  - 状态: 已实现
  - 前端调用: Tasks.tsx ✅ 已集成, Settings.tsx

### 6. 系统统计 API ✅
- `GET /api/v1/evaluation/statistics` - 获取系统统计数据
  - 状态: 已实现（返回初始值）
  - 前端调用: Dashboard.tsx ✅ 已集成

### 7. 系统配置 API ⚠️
- `GET /api/v1/evaluation/config` - 获取系统配置
  - 状态: 需要实现
  - 前端调用: Settings.tsx ✅ 已集成

- `PUT /api/v1/evaluation/config` - 更新系统配置
  - 状态: 需要实现
  - 前端调用: Settings.tsx ✅ 已集成

## 已移除的假数据 ✅

### Dashboard.tsx ✅
- ✅ stats (统计数据) - 已替换为 systemApi.getStatistics()
- ✅ metricScores (指标得分) - 从 statistics API 获取
- ✅ recentTasks (最近任务) - 已替换为 taskApi.list()

### Datasets.tsx ✅
- ✅ datasets (数据集列表) - 已替换为 datasetApi.list()
- ✅ sampleData (样本数据) - 已替换为 datasetApi.getSamples()

### Tasks.tsx ✅
- ✅ tasks (任务列表) - 已集成 taskApi.list()
- ✅ availableMetrics (可用指标) - 已替换为 metricApi.list()

### Reports.tsx ✅
- ✅ reports (报告列表) - 已替换为 reportApi.list()
- ✅ metricTrends (指标趋势) - 已移除（待后端实现）

### Settings.tsx ✅
- ✅ apiConfig (API配置) - 已替换为 systemApi.getConfig/updateConfig()
- ✅ notificationConfig (通知配置) - 已替换为 systemApi.getConfig/updateConfig()
- ⚪ evaluationTemplates (评测模板) - 保留为 UI 预设（不需要动态获取）

## 后端依赖问题

✅ 已解决：
- evaluation_bp 路由已注册
- 依赖已在 requirements.txt 中声明
- 健康检查端点可访问
- 存在 Pydantic 兼容性警告（不影响基础功能）

## 下一步工作

1. 实现真实的评测任务执行逻辑
2. 实现配置持久化存储
3. 添加评测报告生成功能
4. 修复 ChatOpenAI Pydantic 兼容性问题
5. 实现指标趋势统计功能
