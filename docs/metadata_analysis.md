# RAG 系统元数据功能分析

## 一、产品功能概述

### 1. 元数据是什么
元数据（Metadata）是文档的额外属性信息，可以是任意键值对，用于描述文档的特征。例如：
- 文档类型、部门、作者、创建日期等
- 业务相关字段如合同金额、项目编号等

### 2. 产品使用场景

元数据主要用于两个场景：

#### (1) 对话助手配置
在对话助手（Chat）设置中，可以配置元数据过滤方式：

- **禁用**（disabled）：不使用元数据过滤
- **自动**（automatic）：AI 自动根据用户问题生成过滤条件
- **手动**（manual）：用户手动配置过滤条件

#### (2) 检索测试
在知识库的检索测试功能中，可以使用元数据过滤来缩小检索范围。

### 3. 使用流程

**步骤一：设置文档元数据**
- 在文档管理页面，通过 API `/document/set_meta` 为文档设置元数据
- 元数据格式为 JSON 对象，如：`{"department": "sales", "year": "2024"}`
- 支持的值类型：字符串、整数、浮点数

**步骤二：配置元数据过滤**

在对话助手或检索测试中选择过滤方式：

- **自动模式**：
  - AI 分析用户问题和知识库中的元数据
  - 自动生成过滤条件
  - 例如问"2024年的销售报告"，AI 会自动过滤 `year=2024`

- **手动模式**：
  - 用户手动添加过滤条件
  - 支持多种操作符：等于、不等于、包含、不包含、大于、小于等
  - 多个条件之间是 AND 关系

**步骤三：检索时应用过滤**
- 系统根据过滤条件筛选出符合的文档ID
- 只在这些文档中进行向量检索
- 提高检索精度和效率

---

## 二、技术实现详解

### 1. 前端实现

#### 核心组件位置
```
web/src/components/metadata-filter/
├── index.tsx                        # 主入口组件
└── metadata-filter-conditions.tsx   # 条件配置组件
```

#### MetadataFilter 组件 (index.tsx:30-75)
```typescript
export function MetadataFilter({ prefix = '' }: MetadataFilterProps) {
  const kbIds = useWatch({ control: form.control, name: prefix + 'kb_ids' });
  const metadata = useWatch({ control: form.control, name: methodName });

  // 元数据选项：disabled, automatic, manual
  const MetadataOptions = Object.values(DatasetMetadata).map((x) => ({
    value: x,
    label: t(`meta.${x}`),
  }));

  // 根据选择显示手动配置界面
  {metadata === DatasetMetadata.Manual && (
    <MetadataFilterConditions kbIds={kbIds} prefix={prefix} />
  )}
}
```

#### 数据结构
```typescript
// 元数据配置的数据结构
interface MetadataFilterSchema {
  meta_data_filter?: {
    method?: string;    // 'disabled' | 'automatic' | 'manual'
    manual?: Array<{
      key: string;      // 元数据字段名
      op: string;       // 操作符
      value: string;    // 比较值
    }>;
  };
}
```

#### API Hook (hooks/use-knowledge-request.ts:283-298)
```typescript
export function useFetchKnowledgeMetadata(kbIds: string[] = []) {
  const { data } = useQuery({
    queryKey: [KnowledgeApiAction.FetchMetadata, kbIds],
    queryFn: async () => {
      const { data } = await kbService.getMeta({ kb_ids: kbIds.join(',') });
      return data?.data ?? {};
    },
  });
  return { data };
}
```

### 2. 后端实现

#### 元数据获取 API (api/apps/kb_app.py:355-366)
```python
@manager.route("/get_meta", methods=["GET"])
@login_required
def get_meta():
    kb_ids = request.args.get("kb_ids", "").split(",")
    # 权限检查
    for kb_id in kb_ids:
        if not KnowledgebaseService.accessible(kb_id, current_user.id):
            return get_json_result(data=False, message='No authorization.')

    return get_json_result(data=DocumentService.get_meta_by_kbs(kb_ids))
```

#### 元数据存储服务 (api/db/services/document_service.py:656-671)
```python
@classmethod
@DB.connection_context()
def get_meta_by_kbs(cls, kb_ids):
    """
    返回格式：
    {
        "department": {
            "sales": [doc_id1, doc_id2],
            "marketing": [doc_id3]
        },
        "year": {
            "2024": [doc_id1, doc_id3],
            "2023": [doc_id2]
        }
    }
    """
    fields = [cls.model.id, cls.model.meta_fields]
    meta = {}
    for r in cls.model.select(*fields).where(cls.model.kb_id.in_(kb_ids)):
        doc_id = r.id
        for k, v in r.meta_fields.items():
            if k not in meta:
                meta[k] = {}
            v = str(v)
            if v not in meta[k]:
                meta[k][v] = []
            meta[k][v].append(doc_id)
    return meta
```

#### 元数据设置 API (api/apps/document_app.py:703-732)
```python
@manager.route("/set_meta", methods=["POST"])
@login_required
@validate_request("doc_id", "meta")
def set_meta():
    req = request.json
    # 权限检查
    if not DocumentService.accessible(req["doc_id"], current_user.id):
        return get_json_result(data=False, message="No authorization.")

    # 解析并验证元数据
    meta = json.loads(req["meta"])
    if not isinstance(meta, dict):
        return get_json_result(data=False, message="Only dictionary type supported.")

    # 验证值类型（只支持 str, int, float）
    for k, v in meta.items():
        if not isinstance(v, (str, int, float)):
            return get_json_result(data=False, message=f"The type is not supported: {v}")

    # 更新数据库
    DocumentService.update_by_id(req["doc_id"], {"meta_fields": meta})
    return get_json_result(data=True)
```

### 3. 元数据过滤逻辑

#### 手动过滤 (api/db/services/dialog_service.py:485-531)
```python
def meta_filter(metas: dict, filters: list[dict]):
    """
    metas: get_meta_by_kbs 返回的元数据字典
    filters: 过滤条件列表 [{"key": "year", "op": "=", "value": "2024"}]
    返回: 符合条件的文档ID列表
    """
    doc_ids = set([])

    def filter_out(v2docs, operator, value):
        ids = []
        for input, docids in v2docs.items():
            # 支持的操作符
            operations = [
                (operator == "contains", str(value).lower() in str(input).lower()),
                (operator == "not contains", str(value).lower() not in str(input).lower()),
                (operator == "start with", str(input).lower().startswith(str(value).lower())),
                (operator == "end with", str(input).lower().endswith(str(value).lower())),
                (operator == "empty", not input),
                (operator == "not empty", input),
                (operator == "=", input == value),
                (operator == "≠", input != value),
                (operator == ">", input > value),
                (operator == "<", input < value),
                (operator == "≥", input >= value),
                (operator == "≤", input <= value),
            ]
            # 匹配则添加文档ID
            for conds in operations:
                try:
                    if all(conds):
                        ids.extend(docids)
                        break
                except Exception:
                    pass
        return ids

    # 多个条件取交集（AND关系）
    for k, v2docs in metas.items():
        for f in filters:
            if k != f["key"]:
                continue
            ids = filter_out(v2docs, f["op"], f["value"])
            if not doc_ids:
                doc_ids = set(ids)
            else:
                doc_ids = doc_ids & set(ids)  # 交集

    return list(doc_ids)
```

#### AI 自动生成过滤条件 (rag/prompts/prompts.py:424-439)
```python
def gen_meta_filter(chat_mdl, meta_data: dict, query: str) -> list:
    """
    使用 LLM 分析用户问题，自动生成元数据过滤条件
    """
    sys_prompt = PROMPT_JINJA_ENV.from_string(META_FILTER).render(
        current_date=datetime.datetime.today().strftime('%Y-%m-%d'),
        metadata_keys=json.dumps(meta_data),
        user_question=query
    )
    user_prompt = "Generate filters:"

    # 调用 LLM 生成过滤条件
    ans = chat_mdl.chat(sys_prompt, [{"role": "user", "content": user_prompt}])
    ans = re.sub(r"(^.*</think>|```json\n|```\n*$)", "", ans, flags=re.DOTALL)

    try:
        # 解析返回的 JSON 格式过滤条件
        ans = json_repair.loads(ans)
        assert isinstance(ans, list), ans
        return ans
    except Exception:
        logging.exception(f"Loading json failure: {ans}")
    return []
```

#### 在检索中应用 (api/apps/chunk_app.py:307-318)
```python
# 检索测试中应用元数据过滤
if req.get("search_id", ""):
    search_config = SearchService.get_detail(req.get("search_id", "")).get("search_config", {})
    meta_data_filter = search_config.get("meta_data_filter", {})
    metas = DocumentService.get_meta_by_kbs(kb_ids)

    if meta_data_filter.get("method") == "auto":
        # AI 自动生成过滤条件
        filters = gen_meta_filter(chat_mdl, metas, question)
        doc_ids.extend(meta_filter(metas, filters))
    elif meta_data_filter.get("method") == "manual":
        # 手动配置的过滤条件
        doc_ids.extend(meta_filter(metas, meta_data_filter["manual"]))
```

### 4. 数据库存储

#### Document 表结构 (api/db/db_models.py:660-678)
```python
class Document(DataBaseModel):
    id = CharField(max_length=32, primary_key=True)
    kb_id = CharField(max_length=256, null=False, index=True)
    name = CharField(max_length=1024, null=False)
    # ... 其他字段

    # 元数据字段：JSON 格式存储
    meta_fields = JSONField(null=True, default={})
    # 示例数据：{"department": "sales", "year": 2024, "amount": 150000.50}
```

---

## 三、核心工作流程

```
1. 用户问题：「找一下2024年销售部门的合同」
         ↓
2. 获取知识库元数据结构
   GET /kb/get_meta?kb_ids=xxx
   → {
       "department": {"sales": [doc1, doc2], "marketing": [doc3]},
       "year": {"2024": [doc1, doc3], "2023": [doc2]}
     }
         ↓
3. 生成过滤条件（自动或手动）
   - 自动：LLM 分析 → [{"key": "department", "op": "=", "value": "sales"},
                        {"key": "year", "op": "=", "value": "2024"}]
   - 手动：用户配置 → 同上格式
         ↓
4. 应用过滤器
   meta_filter(metas, filters)
   → 返回符合条件的 doc_ids: [doc1]
         ↓
5. 向量检索
   只在 doc1 中进行检索
         ↓
6. 返回结果
   精准匹配用户需求的内容
```

---

## 四、支持的操作符

| 操作符 | 说明 | 示例 |
|--------|------|------|
| = | 等于 | department = "sales" |
| ≠ | 不等于 | status ≠ "archived" |
| > | 大于 | amount > 100000 |
| < | 小于 | year < 2024 |
| ≥ | 大于等于 | score ≥ 90 |
| ≤ | 小于等于 | price ≤ 50000 |
| contains | 包含 | title contains "合同" |
| not contains | 不包含 | content not contains "废弃" |
| start with | 开始于 | code start with "PRJ" |
| end with | 结束于 | file end with ".pdf" |
| empty | 为空 | description empty |
| not empty | 不为空 | author not empty |

---

## 五、总结

### 优点
1. **灵活性**：支持任意键值对，适应各种业务场景
2. **智能化**：AI 自动过滤减少用户配置负担
3. **精准性**：通过元数据预过滤提高检索精度
4. **性能**：减少检索范围，提升检索效率

### 适用场景
- 多部门共享知识库，需要按部门过滤
- 时间敏感的文档查询（如年度报告）
- 业务属性筛选（如合同金额、项目类型）
- 文档状态管理（如草稿、已发布、已归档）

### 关键文件位置
- **前端组件**: `web/src/components/metadata-filter/`
- **后端 API**: `api/apps/kb_app.py`, `api/apps/document_app.py`
- **服务层**: `api/db/services/document_service.py`, `api/db/services/dialog_service.py`
- **数据库模型**: `api/db/db_models.py:660-678`
- **AI 提示词**: `rag/prompts/prompts.py:424-439`

---

## 六、API 接口文档

### 6.1 设置文档元数据
**接口**: `POST /v1/document/set_meta`

**请求参数**:
```json
{
  "doc_id": "文档ID",
  "meta": "{\"department\": \"sales\", \"year\": \"2024\"}"
}
```

**返回示例**:
```json
{
  "code": 0,
  "data": true,
  "message": "success"
}
```

### 6.2 获取知识库元数据
**接口**: `GET /v1/kb/get_meta`

**请求参数**:
- `kb_ids`: 知识库ID列表，逗号分隔

**返回示例**:
```json
{
  "code": 0,
  "data": {
    "department": {
      "sales": ["doc_id1", "doc_id2"],
      "marketing": ["doc_id3"]
    },
    "year": {
      "2024": ["doc_id1", "doc_id3"],
      "2023": ["doc_id2"]
    }
  },
  "message": "success"
}
```

### 6.3 检索测试（带元数据过滤）
**接口**: `POST /v1/retrieval`

**请求参数**:
```json
{
  "question": "用户问题",
  "kb_id": ["知识库ID"],
  "search_id": "检索配置ID",
  "doc_ids": []
}
```

检索配置中包含元数据过滤配置：
```json
{
  "meta_data_filter": {
    "method": "manual",
    "manual": [
      {
        "key": "department",
        "op": "=",
        "value": "sales"
      },
      {
        "key": "year",
        "op": "=",
        "value": "2024"
      }
    ]
  }
}
```

---

*文档生成时间: 2025-10-15*
