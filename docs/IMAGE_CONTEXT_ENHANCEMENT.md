# 图片上下文增强功能说明

## 功能概述

图片上下文增强功能通过从 Markdown 文档中提取图片的上下文信息（章节标题、图片标题、相关段落），为视觉模型提供更丰富的背景信息，从而生成更准确、更有价值的图片描述。

## 实现组件

### 1. 上下文提取器 (`image_context_extractor.py`)

**位置**: `knowflow/server/services/knowledgebases/common/image_context_extractor.py`

**功能**:
- 从 Markdown 文档中提取图片的完整上下文信息
- 支持提取：
  - 图片的 caption（标签/标题）
  - 图片所在的章节标题
  - 图片前面的相关段落（智能匹配）

**关键算法**:
1. **Caption 提取**: 支持 Markdown `![caption](path)` 和 HTML `<img alt="caption">` 格式
2. **标题提取**: 向前查找最近的 `#` 开头的 Markdown 标题
3. **段落提取**（智能匹配）:
   - 向前查找，遇到标题停止
   - 如果**第一个段落**包含"如图X"且匹配 caption → 只返回第一个段落
   - 如果**第二个段落**包含"如图X"且匹配 caption → 只返回第二个段落
   - 如果两个段落都不匹配 → 返回两个段落

**段落匹配示例**:

场景1: 第一个段落匹配
```markdown
## 系统架构
系统采用微服务架构，如图1所示。
<img src="arch.png" alt="图1">
```
→ 只返回："系统采用微服务架构，如图1所示。"

场景2: 第二个段落匹配
```markdown
## 系统架构
本系统基于云原生技术栈构建。
前端使用React，后端采用微服务，如图1所示。
<img src="arch.png" alt="图1">
```
→ 只返回："前端使用React，后端采用微服务，如图1所示。"

场景3: 都不匹配
```markdown
## 系统架构
本系统基于云原生技术栈构建。
前端使用React，后端采用微服务。
<img src="arch.png" alt="图1">
```
→ 返回两个段落：
1. "本系统基于云原生技术栈构建。"
2. "前端使用React，后端采用微服务。"

### 2. 增强的视觉提示词 (`vision_llm_context_describe_prompt.md`)

**位置**: `rag/prompts/zh/vision_llm_context_describe_prompt.md`

**特点**:
- 结合上下文信息指导视觉模型
- 要求模型明确说明图片与上下文的关系
- 提供结构化的输出格式

**提示词渲染函数**: `rag/prompts/prompts.py::vision_llm_context_describe_prompt()`

### 3. RAGFlow 视觉 API 增强 (`llm_app.py`)

**位置**: `api/apps/llm_app.py::vision_describe_batch()`

**修改**:
- API 接收 `context` 参数：`images` 列表中每个图片可以包含 `context` 字段
- 根据是否有 context 选择合适的提示词：
  - 有 context: 使用 `vision_llm_context_describe_prompt(context)`
  - 有自定义 prompt: 使用自定义 prompt
  - 默认: 使用基础的 `describe()` 方法

### 4. 视觉增强服务更新 (`image_vision_enhancer.py`)

**位置**: `knowflow/server/services/knowledgebases/common/image_vision_enhancer.py`

**修改**:
- `enhance_chunks_with_vision()` 新增 `markdown_content` 参数
- 自动调用上下文提取器为每个图片提取上下文
- 将上下文信息传递给 RAGFlow API
- **智能描述插入**: 根据 middle_json 的 caption 合并逻辑，自动将描述插入到正确位置
  - middle_json 生成的图片 markdown 格式：
    ```
    <img src="path" alt="caption">
    caption文本
    ```
  - 新增 `_find_caption_line_end()` 函数检测 caption 行
  - **优化逻辑**：利用 `alt` 属性判断下一行是否是 caption
    - 从 `<img>` 标签提取 `alt` 属性值
    - 将 `alt` 与下一行文本规范化后比较（处理空格差异）
    - 只有当下一行与 `alt` 完全匹配时，才认为是 caption
    - 避免误判：不会把无关文本误认为 caption
  - 如果确认有 caption，描述插入到 caption 之后
  - 如果没有 caption（alt 是默认值或下一行不匹配），直接在图片标签后插入描述
  - 保持与 MinerU/DOTS 解析器生成的文档结构一致

### 5. 智能分块服务集成 (`smart_chunk.py`)

**位置**: `knowflow/server/routes/parse/smart_chunk.py`

**修改**:
- 调用 `enhance_chunks_with_vision()` 时传递完整的 `markdown_text`
- 启用上下文增强功能

## 数据流

```
1. PDF文档
   ↓
2. DOTS/MinerU解析 → 提取图片和 Markdown 文本
   ↓
3. KnowFlow分块服务 (smart_chunk.py)
   ├─ 生成文本分块
   └─ 图片视觉增强 (enable_vision_enhancement=True)
      ├─ 提取图片上下文 (ImageContextExtractor)
      │  ├─ caption: 图片标题
      │  ├─ heading: 所在章节
      │  └─ paragraphs: 相关段落
      ↓
4. 调用 RAGFlow 视觉 API
   ├─ 传递图片路径 + 上下文信息
   ├─ 使用增强的提示词
   └─ deepseek-ai/deepseek-vl2 生成描述
   ↓
5. 将描述插入分块内容
   ↓
6. 存储到知识库
```

## 使用示例

### 输入示例

**Markdown 内容**:
```markdown
## 系统架构

系统采用微服务架构，如图1所示，包含前端、后端和数据库三个主要部分。
前端使用 React 框架开发，提供用户界面。

<img src="/minio/bucket/arch.png" alt="图1: 系统架构图">
图1: 系统架构图

后端采用 Python Flask 框架，负责业务逻辑处理。
```

**提取的上下文**:
```
所在章节：系统架构

图片标题：图1: 系统架构图

相关段落1：系统采用微服务架构，如图1所示,包含前端、后端和数据库三个主要部分。前端使用 React 框架开发，提供用户界面。
```

### 输出示例

**增强后的文档内容**:
```markdown
## 系统架构

系统采用微服务架构，如图1所示，包含前端、后端和数据库三个主要部分。
前端使用 React 框架开发，提供用户界面。

<img src="/minio/bucket/arch.png" alt="图1: 系统架构图">
图1: 系统架构图

[图片描述]: 此图展示了文档中描述的微服务系统架构，包含前端、后端和数据库三个主要部分。前端层采用 React 框架实现用户界面，后端层使用 Python Flask 处理业务逻辑，数据层负责数据存储。该架构采用典型的三层分离设计，有利于系统的扩展和维护。

后端采用 Python Flask 框架，负责业务逻辑处理。
```

**注意**:
- 图片描述会自动插入到 caption 行之后
- caption 和图片描述之间有一个空行，保持格式清晰易读

## 配置说明

### 启用上下文增强

在文档解析配置中启用视觉增强：

```python
parser_config = {
    "enable_vision_enhancement": True,
    "vision_description_format": "[图片描述]: {desc}",
    "vision_batch_size": 3
}
```

### 环境变量

```bash
# RAGFlow API 地址（KnowFlow Server 环境）
RAGFLOW_BASE_URL=http://localhost:9380

# 视觉增强批量大小
VISION_BATCH_SIZE=3
```

## 测试方法

### 1. 准备测试文档

创建一个包含图片的 PDF 文档，确保：
- 有明确的章节标题
- 图片有 caption 或 alt 文本
- 图片前有相关的文本描述

### 2. 上传并解析文档

```bash
# 确保选择了 MinerU 或 DOTS 作为布局解析器
# 确保启用了"图片视觉增强"选项
```

### 3. 查看日志

**KnowFlow Server 日志**:
```bash
docker logs -f knowflow-backend 2>&1 | grep -E "图片.*上下文|context"
```

**RAGFlow Server 日志**:
```bash
docker logs -f <ragflow-container> 2>&1 | grep -E "使用上下文增强|context"
```

### 4. 验证结果

检查生成的分块内容，确认：
- 图片描述包含与上下文相关的信息
- 描述准确反映了图片在文档中的作用
- 描述质量明显优于无上下文的版本

## 故障排查

### 问题1: 上下文未提取

**症状**: 日志显示"未提供 markdown_content，将不使用上下文增强"

**解决**:
- 确认使用的是 MinerU 或 DOTS 解析器（Plain Text 不生成 Markdown）
- 检查 `smart_chunk.py` 是否正确传递 `markdown_text` 参数

### 问题2: 视觉模型超时/失败

**症状**: API 调用失败或超时

**解决**:
- 检查 `tenant.img2txt_id` 是否设置为 `deepseek-ai/deepseek-vl2@SILICONFLOW`
- 验证 SILICONFLOW API 密钥是否有效
- 查看 RAGFlow 日志中的详细错误信息

### 问题3: 上下文提取不准确

**症状**: 提取的段落或标题不相关

**解决**:
- 检查 Markdown 格式是否规范（标题使用 `#`，段落用空行分隔）
- 调整 `ImageContextExtractor` 的匹配逻辑
- 在日志中查看提取的上下文内容，手动验证

## 性能优化建议

1. **批量处理**: 使用合适的 `vision_batch_size`（推荐 3-5）
2. **缓存**: 对相同图片的描述可以缓存复用
3. **并行处理**: 多页文档可以并行处理多个批次
4. **超时设置**: 确保 API 超时设置合理（当前 120 秒）

## 未来改进方向

1. **多语言支持**: 根据文档语言自动选择提示词
2. **上下文优化**: 更智能的段落选择算法
3. **模型选择**: 支持根据图片类型自动选择合适的视觉模型
4. **增量更新**: 只对新图片或修改的图片重新生成描述
