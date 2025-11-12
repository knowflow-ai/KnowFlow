# PaddleOCR 接入技术设计

## 1. 概述

本文档描述如何将 PaddleOCR 接入 KnowFlow 架构，实现与 MinerU/DOTS 相同的功能：
- PDF 解析
- 文档分块
- 坐标溯源

## 2. PaddleOCR API 分析

### 2.1 API 端点

```
POST http://8.134.177.47:15003/layout-parsing
```

### 2.2 请求格式

```json
{
  "file": "base64编码的图片或PDF",
  "fileType": 1  // 0=PDF, 1=图片
}
```

### 2.3 响应格式

```json
{
  "logId": "uuid",
  "errorCode": 0,
  "errorMsg": "Success",
  "result": {
    "layoutParsingResults": [
      {
        "markdown": {
          "text": "完整的 Markdown 文本",
          "images": {},
          "isStart": null,
          "isEnd": null
        },
        "prunedResult": {
          "model_settings": {...},
          "parsing_res_list": [
            {
              "block_label": "paragraph_title" | "text" | "table" | "image",
              "block_content": "文本内容",
              "block_bbox": [x0, y0, x1, y1],
              "block_id": 0,
              "block_order": 1
            },
            ...
          ],
          "layout_det_res": {...}
        },
        "outputImages": {
          "layout_det_res": "base64...",
          "layout_order_res": "base64..."
        },
        "inputImage": "base64..."
      }
    ],
    "dataInfo": {
      "type": "image",
      "width": 1920,
      "height": 1080
    }
  }
}
```

### 2.4 核心数据结构

#### parsing_res_list (块级结构)

```python
{
  "block_label": str,      # 块类型
  "block_content": str,    # 块内容
  "block_bbox": [x0, y0, x1, y1],  # 块坐标
  "block_id": int,         # 块ID
  "block_order": int       # 阅读顺序
}
```

#### markdown.text (完整 Markdown)

```markdown
## 标题

段落文本

<table>...</table>
```

## 3. 关键挑战

### 3.1 PaddleOCR 与 MinerU 的差异

| 特性 | MinerU | PaddleOCR | 影响 |
|------|--------|-----------|------|
| 输出粒度 | 行级（lines/spans） | 块级（blocks） | ⚠️ 坐标精度降低 |
| 坐标系统 | 72 DPI PDF 坐标 | 200 DPI 图像坐标 | ⚠️ 需要坐标转换 |
| 输入格式 | PDF (multi-page) | 图片 (single page) | ⚠️ 需要 PDF → 图片转换 |
| 文本层级 | spans → lines → blocks | blocks only | ⚠️ 无法获取行级坐标 |
| 表格处理 | 提取单元格级结构 | 返回 HTML 字符串 | ⚠️ 表格内坐标不精确 |

### 3.2 坐标溯源问题

**MinerU 的优势**:
```python
# MinerU 提供行级坐标
{
  "lines": [
    {
      "bbox": [100, 200, 500, 215],  # 第一行的精确坐标
      "spans": [{"content": "第一行"}]
    },
    {
      "bbox": [100, 215, 500, 230],  # 第二行的精确坐标
      "spans": [{"content": "第二行"}]
    }
  ]
}
```

**PaddleOCR 的限制**:
```python
# PaddleOCR 只提供块级坐标
{
  "block_bbox": [100, 200, 500, 230],  # 整个块的坐标
  "block_content": "第一行\n第二行"       # 无法区分每一行
}
```

**解决方案**:
- 对于语义块级别（semantic）：直接使用块级坐标 ✅
- 对于逐行级别（line）：使用块级坐标分配给所有行 ⚠️（精度降低）

### 3.3 PDF 多页处理

PaddleOCR 接受单张图片，需要：
1. 将 PDF 转换为多张图片（每页一张）
2. 逐页调用 PaddleOCR
3. 合并所有页面结果

**技术选型**: `pdf2image` (Python 库)

```python
from pdf2image import convert_from_path

images = convert_from_path(
    pdf_path,
    first_page=from_page + 1,
    last_page=to_page + 1,
    dpi=200  # 匹配 PaddleOCR 坐标系
)
```

## 4. 架构设计

### 4.1 整体流程

```
用户上传 PDF
    ↓
[RAGFlow] ensure_pdf() - 确保是 PDF
    ↓
[RAGFlow] PaddleOCRParser.__call__()
    → POST /api/parse/paddleocr
    → 发送: PDF binary
    ↓
[KnowFlow] parse_with_paddleocr()
    → PDF → 图片 (pdf2image)
    → 逐页调用 PaddleOCR API
    → 合并页面结果
    → 转换为 pseudo-middle.json
    ↓
[KnowFlow] 复用 SimpleMiddleJsonConverter
    → 生成 markdown + coordinate_map
    ↓
[KnowFlow] 返回给 RAGFlow
    → boxes (语义块)
    → markdown (完整文本)
    → coordinate_map (块级坐标)
    ↓
[RAGFlow] 后续流程同 MinerU
    → Smart Chunking
    → 坐标附加
    → 转换为 RAGFlow 格式
```

### 4.2 pseudo-middle.json 设计

由于 PaddleOCR 不提供行级数据，我们创建一个"伪 middle.json"：

```python
{
  "pdf_info": [
    {
      "page_idx": 0,
      "para_blocks": [  # 使用 para_blocks（虽然不是真正的段落）
        {
          "type": "text",
          "bbox": [x0, y0, x1, y1],  # 块级坐标
          "lines": [  # ⚠️ 伪造的行级结构
            {
              "bbox": [x0, y0, x1, y1],  # 与块相同
              "spans": [
                {
                  "type": "text",
                  "content": "块内容（可能包含多行）",
                  "bbox": [x0, y0, x1, y1]
                }
              ]
            }
          ],
          "_paddleocr_block": {  # 保留原始 PaddleOCR 数据
            "block_label": "paragraph_title",
            "block_id": 0,
            "block_order": 1
          }
        }
      ]
    }
  ]
}
```

**设计理由**:
1. **兼容性**: 保持与 MinerU middle.json 相同的结构，可以复用 `SimpleMiddleJsonConverter`
2. **简化**: 每个块创建一个"伪行"，避免修改转换器代码
3. **扩展性**: 通过 `_paddleocr_block` 保留原始信息，便于调试

### 4.3 坐标转换策略

#### 策略 1: 块级坐标 (默认)

```python
# PaddleOCR 块
{
  "block_content": "第一行\n第二行\n第三行",
  "block_bbox": [100, 200, 500, 300]
}

# 转换为 coordinate_map（所有行使用相同坐标）
{
  0: [0, 100, 500, 200, 300],  # 第一行
  1: [0, 100, 500, 200, 300],  # 第二行
  2: [0, 100, 500, 200, 300]   # 第三行
}
```

**优点**: 实现简单，不会丢失块级信息
**缺点**: 无法精确定位到行，坐标重复

#### 策略 2: 估算行坐标 (未来优化)

```python
# 根据行数估算每行的垂直坐标
num_lines = 3
line_height = (y1 - y0) / num_lines

coordinate_map = {
  0: [0, 100, 500, 200, 200 + line_height],      # 第一行
  1: [0, 100, 500, 200 + line_height, 200 + 2*line_height],  # 第二行
  2: [0, 100, 500, 200 + 2*line_height, 300]     # 第三行
}
```

**优点**: 坐标更精确
**缺点**: 估算可能不准确（行高不均匀）

**本次实现**: 采用策略 1（简单可靠）

## 5. 模块设计

### 5.1 文件结构

```
knowflow/server/services/knowledgebases/paddleocr_parse/
├── __init__.py
├── paddleocr_client.py           # PaddleOCR API 客户端
├── pdf_to_images.py              # PDF 转图片
├── ocr_to_middle_json.py         # OCR 结果转 pseudo-middle.json
└── coordinate_mapper.py          # 坐标转换工具

knowflow/server/routes/parse/
└── paddleocr.py                  # Flask 路由

deepdoc/parser/
└── paddleocr_parser.py           # RAGFlow Parser
```

### 5.2 核心类设计

#### PaddleOCRClient

```python
class PaddleOCRClient:
    """PaddleOCR API 客户端"""

    def __init__(self, api_url: str = "http://8.134.177.47:15003"):
        self.api_url = api_url
        self.endpoint = f"{api_url}/layout-parsing"

    def recognize_image(self, image_binary: bytes, timeout: int = 120) -> dict:
        """
        识别单张图片

        Returns:
            {
                "markdown": str,
                "blocks": [{"block_label": ..., "block_content": ..., "block_bbox": ...}],
                "images": {...}
            }
        """

    def recognize_pdf_pages(self, pdf_path: str, from_page: int, to_page: int) -> List[dict]:
        """
        识别 PDF 多页

        Returns:
            [page0_result, page1_result, ...]
        """
```

#### OCRToMiddleJsonConverter

```python
class OCRToMiddleJsonConverter:
    """将 PaddleOCR 结果转换为 pseudo-middle.json"""

    def convert(self, ocr_pages: List[dict]) -> dict:
        """
        Args:
            ocr_pages: PaddleOCR 逐页结果

        Returns:
            pseudo-middle.json
        """

    def _convert_block_to_para_block(self, block: dict, page_idx: int) -> dict:
        """将 PaddleOCR block 转换为 para_block"""
```

## 6. 实现步骤

### Phase 1: 基础架构 ✅ (当前阶段)

1. [x] 分析 PaddleOCR API 格式
2. [x] 设计 pseudo-middle.json 结构
3. [x] 规划模块结构
4. [ ] 创建技术设计文档

### Phase 2: KnowFlow Server 端实现

1. [ ] 实现 `PaddleOCRClient`
2. [ ] 实现 PDF 转图片工具
3. [ ] 实现 `OCRToMiddleJsonConverter`
4. [ ] 创建 `/api/parse/paddleocr` 端点
5. [ ] 测试 KnowFlow Server 端

### Phase 3: RAGFlow 端实现

1. [ ] 实现 `PaddleOCRParser`
2. [ ] 在 `ModernParserBase` 中注册
3. [ ] 测试完整流程

### Phase 4: 集成测试

1. [ ] 测试 Smart Chunking
2. [ ] 验证坐标溯源
3. [ ] 性能测试
4. [ ] 边界情况测试

## 7. 预期限制

### 7.1 坐标精度

- **MinerU**: 行级精度（每行都有独立坐标）
- **PaddleOCR**: 块级精度（一个段落内所有行共享坐标）

**影响**:
- 在 PDF 查看器中高亮时，可能会选中整个段落而非特定行
- Smart Chunking 的坐标映射可能不如 MinerU 精确

### 7.2 性能

**PDF 转图片开销**:
- 100 页 PDF，200 DPI
- 预计耗时: 10-20 秒（取决于服务器性能）

**PaddleOCR 调用**:
- 单页耗时: 3-5 秒
- 100 页总耗时: 5-8 分钟

**建议**:
- 异步处理
- 任务队列
- 进度回调

### 7.3 表格处理

PaddleOCR 返回的表格是 HTML 字符串，无法获取单元格级坐标。

**解决方案**:
- 使用整个表格的 bbox
- 表格内部不支持精确定位

## 8. 测试计划

### 8.1 单元测试

- `PaddleOCRClient.recognize_image()`
- `OCRToMiddleJsonConverter.convert()`
- `pdf_to_images()`

### 8.2 集成测试

- KnowFlow Server API 端到端测试
- RAGFlow Parser 测试
- 坐标映射准确性测试

### 8.3 测试用例

1. **简单 PDF**: 纯文本，单页
2. **多页 PDF**: 10 页文档
3. **复杂布局**: 多列、表格、图片
4. **中英混合**: 测试 OCR 准确性
5. **扫描文档**: 测试 OCR 鲁棒性

## 9. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| PaddleOCR API 不稳定 | 中 | 高 | 添加重试机制、超时控制 |
| 坐标精度不足 | 高 | 中 | 文档说明限制，未来优化行级坐标估算 |
| PDF 转图片慢 | 中 | 中 | 异步处理、缓存机制 |
| 内存占用大 | 中 | 低 | 流式处理、及时释放图片 |

## 10. 未来优化

1. **行级坐标估算**: 根据行数和块高度估算每行坐标
2. **并行处理**: 多页并行调用 PaddleOCR
3. **缓存机制**: 缓存 PDF 转图片结果
4. **增量更新**: 只处理修改的页面
5. **GPU 加速**: 使用 GPU 加速 OCR 和图片转换
