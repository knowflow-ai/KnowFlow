# MinerU/DOTS 架构重构方案

> 更新时间：2025-10-02
> 状态：设计阶段 → 实施中

## 1. 当前架构分析

### RAGFlow 原有架构
- **PDF 解析器**（`parser_config.layout_recognize`）：DeepDOC、Plain Text、VLM
  - 位置：`deepdoc/parser/pdf_parser.py`
  - 负责：PDF OCR、布局识别、内容提取

- **文件解析方法**（`parser_id`）：naive, paper, manual, book, qa, table 等
  - 位置：`rag/app/*.py`
  - 负责：分块策略、内容处理
  - 注册：`rag/svr/task_executor.py` 的 `FACTORY` 字典

### 当前 MinerU/DOTS 实现问题
- ❌ 被定义为文件解析方法（`ParserType.MINERU/DOTS`）
- ❌ 未在 FACTORY 中注册，绕过 RAGFlow 任务队列
- ❌ 前端直接调用 knowflow server API
- ❌ 无法与 RAGFlow 现有解析方法（naive/paper 等）组合使用

---

## 2. 新架构设计

### 核心理念
**MinerU/DOTS = PDF 解析器（负责 OCR）+ 分块策略（负责 chunking）**

### 架构层次
```
┌─────────────────────────────────────────────────────┐
│  前端选择                                            │
│  - PDF 解析器: DeepDOC / PlainText / MinerU / DOTS  │
│  - 文件解析方法: naive / paper / smart / regex 等    │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  RAGFlow Task Queue (api/apps, rag/svr)            │
│  - 统一任务调度                                      │
│  - 进度跟踪                                          │
└─────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────┬──────────────────────────────┐
│  PDF 解析器层         │  文件解析方法层               │
│  (deepdoc/parser)    │  (rag/app)                   │
│                      │                              │
│  - RAGFlowPdfParser  │  - naive.py (general)        │
│  - PlainParser       │  - paper.py                  │
│  - MinerUParser ⭐   │  - manual.py                 │
│  - DOTSParser ⭐     │  - smart.py ⭐ (新增)        │
│                      │  - regex.py ⭐ (新增)        │
└──────────────────────┴──────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  KnowFlow Server API (HTTP 跨容器调用)              │
│  - /api/parse/mineru  → MinerU OCR 服务             │
│  - /api/parse/dots    → DOTS OCR 服务               │
│  - /api/chunk/smart   → 智能分块服务 ⭐             │
│  - /api/chunk/regex   → 正则分块服务 ⭐             │
└─────────────────────────────────────────────────────┘
```

---

## 3. 第一阶段实施计划（MVP）

### 范围
✅ MinerU PDF 解析器
✅ General (naive) 文件解析方法 + MinerU 解析器组合
❌ DOTS（待第二阶段）
❌ 其他分块策略（待验证后扩展）

### 具体改动

#### 3.1 后端 - RAGFlow

**文件：`deepdoc/parser/mineru_parser.py`** （新建）
```python
class MinerUParser:
    """MinerU PDF 解析器，通过 HTTP 调用 KnowFlow Server"""

    def __call__(self, filename, binary=None, from_page=0, to_page=100000):
        # 调用 KnowFlow Server MinerU API
        # 返回统一格式的解析结果（boxes, images, tables）
```

**文件：`deepdoc/parser/__init__.py`**
- 导出 `MinerUParser`

**文件：`rag/app/naive.py`**
- 修改 PDF 部分，支持从 `parser_config.layout_recognize` 读取解析器
- 添加 MinerU 解析器支持

**文件：`api/db/__init__.py`**
- 添加 `LayoutRecognizeType` 枚举（可选，用于明确 PDF 解析器类型）

#### 3.2 后端 - KnowFlow Server

**文件：`knowflow/server/routes/parse/__init__.py`** （新建）
- 注册解析 API 路由

**文件：`knowflow/server/routes/parse/mineru.py`** （新建）
```python
@router.post('/api/parse/mineru')
def parse_with_mineru(file: UploadFile, config: dict):
    """MinerU PDF 解析服务

    返回格式：
    {
        "boxes": [...],  # OCR 文本框
        "images": [...], # 图片
        "tables": [...], # 表格
        "middle_json": {...}  # 原始 middle.json
    }
    """
```

#### 3.3 前端

**文件：`web/src/components/layout-recognize.tsx`**
- 添加 MinerU 选项到下拉列表
```tsx
const options = [
  { label: 'DeepDoc', value: 'DeepDOC' },
  { label: 'Plain Text', value: 'Plain Text' },
  { label: 'MinerU', value: 'MinerU' }, // 新增
  ...image2TextList
];
```

**文件：`web/src/constants/knowledge.ts`**
- 从 `DocumentParserType` 枚举中**移除** `MinerU` 和 `DOTS`
- 添加 `LayoutRecognizeType` 枚举（可选）

**文件：`web/src/pages/add-knowledge/components/knowledge-setting/configuration/`**
- 移除 DOTS 专属配置页面（或改造为通用配置）
- General 配置页保持不变（已有 LayoutRecognize 组件）

#### 3.4 数据库迁移

**无需迁移**
- `parser_config.layout_recognize` 字段已存在
- 只需前端传值改为 "MinerU"

---

## 4. 关键技术点

### 4.1 跨容器 HTTP 调用
```python
# deepdoc/parser/mineru_parser.py
import requests
from api import settings

KNOWFLOW_SERVER_URL = os.getenv('KNOWFLOW_SERVER_URL', 'http://knowflow-server:5000')

def call_mineru_api(binary, config):
    response = requests.post(
        f"{KNOWFLOW_SERVER_URL}/api/parse/mineru",
        files={"file": binary},
        data={"config": json.dumps(config)}
    )
    return response.json()
```

### 4.2 解析结果格式统一
所有 PDF 解析器（DeepDOC、PlainText、MinerU）返回格式：
```python
{
    "boxes": [
        {
            "text": "...",
            "x0": 0, "x1": 100, "top": 0, "bottom": 20,
            "page_number": 0,
            "layout_type": "text"  # text/title/table/figure
        }
    ],
    "images": [...],
    "tables": [...]
}
```

### 4.3 任务队列集成
- MinerU 解析通过 RAGFlow 任务队列
- 进度回调：`callback(prog=0.5, msg="MinerU parsing...")`
- 错误处理：统一异常捕获

---

## 5. 第二阶段扩展计划（待验证后）

### 5.1 DOTS PDF 解析器
- 复制 MinerU 实现，调用 DOTS API

### 5.2 新增分块策略
- `rag/app/smart.py` - 智能分块（调用 KnowFlow Server）
- `rag/app/regex.py` - 正则分块
- `rag/app/title.py` - 标题分块
- `rag/app/parent_child.py` - 父子分块

### 5.3 前端完整支持
- 文件解析方法下拉列表添加：smart、regex、title、parent_child
- 各解析方法的配置表单

---

## 6. 兼容性保障

### 向后兼容
- ✅ 现有 DeepDOC + naive 组合不受影响
- ✅ 现有 parser_config 格式保持兼容
- ✅ 数据库无需迁移

### 平滑迁移
1. 保留 `DocumentParserType.MINERU/DOTS`（标记为 deprecated）
2. 前端显示迁移提示："MinerU 已升级为 PDF 解析器，请在布局识别中选择"
3. 后端检测到旧配置时自动转换

---

## 7. 测试计划

### 单元测试
- MinerU 解析器 HTTP 调用
- 解析结果格式转换
- 错误处理

### 集成测试
- MinerU + naive 完整流程
- 任务队列调度
- 进度跟踪

### 端到端测试
- 前端上传 PDF → 选择 MinerU + General → 解析成功
- 对比 MinerU vs DeepDOC 解析质量

---

## 8. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 跨容器网络不通 | 高 | 本地测试验证，docker-compose 配置检查 |
| KnowFlow Server 性能瓶颈 | 中 | 添加超时、重试机制，监控响应时间 |
| 格式转换不兼容 | 中 | 完整的单元测试覆盖，逐步验证 |
| 前端迁移用户困惑 | 低 | 清晰的 UI 提示，文档说明 |

---

## 9. 开发工作量估算

| 任务 | 工作量 | 优先级 |
|------|--------|--------|
| MinerU 解析器实现 | 2 天 | P0 |
| KnowFlow Server API | 1 天 | P0 |
| naive.py 适配 | 1 天 | P0 |
| 前端 layout-recognize 修改 | 0.5 天 | P0 |
| 前端枚举清理 | 0.5 天 | P0 |
| 测试 | 2 天 | P0 |
| **第一阶段总计** | **7 天** | - |

---

## 10. 实施进度

### 已完成
- ✅ 架构设计分析
- ✅ 方案评审

### 进行中
- 🔄 MinerU 解析器开发

### 待开始
- 🔲 KnowFlow Server API 开发
- 🔲 naive.py 适配
- 🔲 前端改造
- 🔲 集成测试
- 🔲 部署验证
