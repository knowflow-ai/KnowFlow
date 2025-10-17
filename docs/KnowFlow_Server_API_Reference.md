# KnowFlow Server API Reference

完整的 KnowFlow Server RESTful API 参考文档。KnowFlow Server 是独立的企业级服务，提供用户管理、团队协作、RBAC权限控制和增强的文档解析功能。

**版本**: v2.1.5
**最后更新**: January 2025
**基础**: RAGFlow v0.20.1

---

## 目录

1. [简介](#简介)
2. [认证](#认证)
3. [错误码](#错误码)
4. [认证管理 APIs](#认证管理-apis)
5. [用户管理 APIs](#用户管理-apis)
6. [团队管理 APIs](#团队管理-apis)
7. [租户管理 APIs](#租户管理-apis)
8. [知识库管理 APIs](#知识库管理-apis)
9. [文档管理 APIs](#文档管理-apis)
10. [文件管理 APIs](#文件管理-apis)
11. [RBAC权限管理 APIs](#rbac权限管理-apis)
12. [文档解析服务 APIs](#文档解析服务-apis)
13. [代码示例](#代码示例)
14. [最佳实践](#最佳实践)

---

## 简介

### KnowFlow Server vs RAGFlow

**RAGFlow** (端口 9380):
- 核心RAG引擎
- 文档解析和分块
- 向量检索
- 对话管理

**KnowFlow Server** (端口 5000):
- 用户和团队管理
- 基于角色的访问控制(RBAC)
- 知识库级别的权限管理
- 增强的文档解析服务（MinerU/DOTS）
- 多租户支持

### 架构关系

```
用户请求 → KnowFlow Server (认证/权限) → RAGFlow (核心处理)
                ↓
           用户/团队/权限数据库
```

---

## 认证

KnowFlow Server 支持两种认证方式：

### 1. API Key 认证（推荐）

```bash
Authorization: Bearer <YOUR_API_KEY>
```

从 RAGFlow 获取 API Key:
1. 登录 RAGFlow Web 界面
2. 设置 > API Key
3. 复制 API Key

### 2. JWT Token 认证

```bash
Authorization: <JWT_TOKEN>
```

通过登录接口获取 JWT Token（用于 KnowFlow Server 内部管理界面）。

---

## Base URLs

```
KnowFlow Server: http://localhost:5000
RAGFlow:         http://localhost:9380
```

---

## 错误码

| Code | Message | Description |
|------|---------|-------------|
| 0 | Success | 请求成功 |
| 102 | Invalid Parameter | 参数缺失或无效 |
| 109 | Permission Denied | 权限不足 |
| 400 | Bad Request | 请求格式错误 |
| 401 | Unauthorized | 未授权访问 |
| 403 | Forbidden | 禁止访问 |
| 404 | Not Found | 资源不存在 |
| 500 | Internal Server Error | 服务器内部错误 |
| 503 | Service Unavailable | 服务不可用（RBAC初始化中） |

---

## 认证管理 APIs

### Health Check

**GET** `/health`

检查 KnowFlow Server 的健康状态。

#### Request

- Method: GET
- URL: `/health`
- **无需认证**

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/health
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "status": "healthy",
    "database_ready": true,
    "required_tables": {
      "user": true,
      "tenant": true,
      "user_tenant": true
    },
    "rbac_initialized": true,
    "timestamp": "2025-01-17T00:00:00.000000"
  },
  "message": "服务运行正常"
}
```

Initializing (HTTP 503):

```json
{
  "code": 1,
  "data": {
    "status": "initializing",
    "database_ready": false,
    "missing_tables": ["rbac_roles", "rbac_permissions"],
    "rbac_initialized": false,
    "timestamp": "2025-01-17T00:00:00.000000"
  },
  "message": "服务正在初始化"
}
```

---

### Get RBAC Status

**GET** `/api/v1/admin/rbac/status`

获取 RBAC 系统的详细状态信息。

#### Request

- Method: GET
- URL: `/api/v1/admin/rbac/status`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/admin/rbac/status \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "database_ready": true,
    "required_tables": {
      "user": true,
      "tenant": true,
      "user_tenant": true
    },
    "rbac_initialized": true,
    "background_init_status": true,
    "system_roles_count": 5,
    "permissions_count": 15,
    "default_admin_exists": true,
    "timestamp": "2025-01-17T00:00:00"
  },
  "message": "获取RBAC状态成功"
}
```

---

### Initialize RBAC System

**POST** `/api/v1/admin/rbac/init`

手动触发 RBAC 系统初始化（通常由系统自动完成）。

#### Request

- Method: POST
- URL: `/api/v1/admin/rbac/init`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/admin/rbac/init \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "RBAC系统初始化成功",
  "data": {
    "admin_account": "admin@gmail.com",
    "admin_password": "admin"
  }
}
```

---

## 用户管理 APIs

### Get Current User

**GET** `/api/v1/users/me`

获取当前登录用户的信息。

#### Request

- Method: GET
- URL: `/api/v1/users/me`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>` (RAGFlow API Key)

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/users/me \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "69736c5e723611efb51b0242ac120007",
    "username": "管理员",
    "email": "admin@gmail.com",
    "roles": ["admin", "super_admin"],
    "role": "super_admin"
  },
  "message": "获取用户信息成功"
}
```

**Note**: 需要使用从 RAGFlow 获取的有效 JWT Token 或 API Key。

---

### List Users

**GET** `/api/v1/users`

获取用户列表（支持分页和筛选）。

#### Request

- Method: GET
- URL: `/api/v1/users?current_page={page}&size={size}&username={username}&email={email}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:5000/api/v1/users?current_page=1&size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `current_page` (*Query parameter*) `integer`
  - 当前页码
  - Default: 1

- `size` (*Query parameter*) `integer`
  - 每页数量
  - Default: 10
  - Range: 1-100

- `username` (*Query parameter*) `string`
  - 按用户名筛选（模糊匹配）

- `email` (*Query parameter*) `string`
  - 按邮箱筛选（模糊匹配）

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "id": "69736c5e723611efb51b0242ac120007",
        "email": "admin@gmail.com",
        "nickname": "管理员",
        "status": "1",
        "is_superuser": 1,
        "create_time": "2024-10-01T10:00:00",
        "update_time": "2024-10-01T10:00:00"
      }
    ],
    "total": 1
  },
  "message": "获取用户列表成功"
}
```

**RBAC Authorization**:
- 超级管理员：查看所有用户
- 普通管理员：查看自己创建的用户
- 普通用户：仅查看自己

---

### List Assignable Users

**GET** `/api/v1/users/assignable`

获取可分配权限的用户列表（排除超级管理员）。

#### Request

- Method: GET
- URL: `/api/v1/users/assignable?current_page={page}&size={size}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:5000/api/v1/users/assignable?current_page=1&size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Same format as List Users, but excludes super admins.

---

### Create User

**POST** `/api/v1/users`

创建新用户。

#### Request

- Method: POST
- URL: `/api/v1/users`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/users \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "email": "newuser@example.com",
       "password": "SecurePass@123",
       "nickname": "New User",
       "status": "1"
     }'
```

##### Request Parameters

- `email` (*Body parameter*) `string`, **Required**
  - 用户邮箱（作为唯一标识）
  - 必须是有效的邮箱格式
  - 不能与现有用户重复

- `password` (*Body parameter*) `string`, **Required**
  - 用户密码
  - 建议至少8位，包含大小写字母和数字

- `nickname` (*Body parameter*) `string`
  - 用户昵称/显示名
  - 默认使用邮箱前缀

- `status` (*Body parameter*) `string`
  - 用户状态
  - `"1"`: 激活（default）
  - `"0"`: 禁用

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "用户创建成功"
}
```

Failure - Duplicate Email (HTTP 400):

```json
{
  "code": 400,
  "message": "邮箱已存在"
}
```

**Note**: 新创建的用户默认需要登录后才能设置权限。

---

### Update User

**PUT** `/api/v1/users/{user_id}`

更新用户信息。

#### Request

- Method: PUT
- URL: `/api/v1/users/{user_id}`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:5000/api/v1/users/69736c5e723611efb51b0242ac120007 \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "nickname": "Updated Nickname",
       "status": "1"
     }'
```

##### Request Parameters

- `user_id` (*Path parameter*) `string`, **Required**
  - 用户ID

- `nickname` (*Body parameter*) `string`
  - 新的用户昵称

- `status` (*Body parameter*) `string`
  - 新的用户状态
  - `"1"`: 激活
  - `"0"`: 禁用

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "用户更新成功"
}
```

---

### Reset User Password

**PUT** `/api/v1/users/{user_id}/reset-password`

重置用户密码。

#### Request

- Method: PUT
- URL: `/api/v1/users/{user_id}/reset-password`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:5000/api/v1/users/69736c5e723611efb51b0242ac120007/reset-password \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "password": "NewSecurePass@456"
     }'
```

##### Request Parameters

- `user_id` (*Path parameter*) `string`, **Required**
  - 用户ID

- `password` (*Body parameter*) `string`, **Required**
  - 新密码

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "用户密码重置成功"
}
```

---

### Assign Role to User

**POST** `/api/v1/users/{user_id}/roles`

为用户分配角色。

#### Request

- Method: POST
- URL: `/api/v1/users/{user_id}/roles`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/users/69736c5e723611efb51b0242ac120007/roles \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "role_code": "admin",
       "tenant_id": "default",
       "resource_type": "knowledgebase",
       "resource_id": "kb_12345"
     }'
```

##### Request Parameters

- `user_id` (*Path parameter*) `string`, **Required**
  - 用户ID

- `role_code` (*Body parameter*) `string`, **Required**
  - 角色代码
  - 可选值: `super_admin`, `admin`, `editor`, `viewer`, `user`

- `tenant_id` (*Body parameter*) `string`
  - 租户ID
  - Default: `"default"`

- `resource_type` (*Body parameter*) `string`
  - 资源类型
  - 可选值: `"knowledgebase"`, `"document"`, `"team"`
  - 不指定则为全局角色

- `resource_id` (*Body parameter*) `string`
  - 资源ID
  - 配合 `resource_type` 使用

- `expires_at` (*Body parameter*) `string` (ISO 8601)
  - 角色过期时间
  - 示例: `"2025-12-31T23:59:59Z"`

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "成功为用户分配角色: admin"
}
```

---

### Revoke User Role

**DELETE** `/api/v1/users/{user_id}/roles/{role_code}`

撤销用户的角色。

#### Request

- Method: DELETE
- URL: `/api/v1/users/{user_id}/roles/{role_code}?tenant_id={tenant_id}&resource_id={resource_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url 'http://localhost:5000/api/v1/users/69736c5e723611efb51b0242ac120007/roles/admin?tenant_id=default' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Request Parameters

- `user_id` (*Path parameter*) `string`, **Required**
  - 用户ID

- `role_code` (*Path parameter*) `string`, **Required**
  - 角色代码

- `tenant_id` (*Query parameter*) `string`
  - 租户ID
  - Default: `"default"`

- `resource_id` (*Query parameter*) `string`
  - 资源ID（如果是资源级角色）

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "成功撤销用户角色: admin"
}
```

---

### Delete User

**DELETE** `/api/v1/users/{user_id}`

删除用户。

#### Request

- Method: DELETE
- URL: `/api/v1/users/{user_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:5000/api/v1/users/69736c5e723611efb51b0242ac120007 \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "用户 69736c5e723611efb51b0242ac120007 删除成功"
}
```

**Warning**: 删除用户会同时删除其所有角色和权限关系。

---

## 团队管理 APIs

> **注意**: 团队成员的添加功能实际通过 RAGFlow 的租户 API (`POST /v1/tenant/{team_id}/user`) 实现。团队在系统中被当做租户使用，成员管理复用了 RAGFlow 的租户用户管理功能。

### List Teams

**GET** `/api/v1/teams`

获取团队列表。

#### Request

- Method: GET
- URL: `/api/v1/teams?current_page={page}&size={size}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:5000/api/v1/teams?current_page=1&size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `current_page` (*Query parameter*) `integer`
  - 当前页码
  - Default: 1

- `size` (*Query parameter*) `integer`
  - 每页数量
  - Default: 10

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "id": "team_12345",
        "name": "开发团队",
        "description": "负责系统开发",
        "creator_id": "user_123",
        "member_count": 5,
        "create_time": "2025-01-01T10:00:00",
        "update_time": "2025-01-15T10:00:00"
      }
    ],
    "total": 1
  },
  "message": "获取团队列表成功"
}
```

---

### Create Team

**POST** `/api/v1/teams`

创建新团队。

#### Request

- Method: POST
- URL: `/api/v1/teams`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/teams \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "name": "开发团队",
       "description": "负责系统开发和维护"
     }'
```

##### Request Parameters

- `name` (*Body parameter*) `string`, **Required**
  - 团队名称
  - 必须唯一

- `description` (*Body parameter*) `string`
  - 团队描述

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "team_12345",
    "name": "开发团队",
    "description": "负责系统开发和维护",
    "creator_id": "user_123",
    "create_time": "2025-01-17T10:00:00"
  },
  "message": "创建团队成功"
}
```

---

### Get Team Details

**GET** `/api/v1/teams/{team_id}`

获取团队详细信息。

#### Request

- Method: GET
- URL: `/api/v1/teams/{team_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/teams/team_12345 \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "team_12345",
    "name": "开发团队",
    "description": "负责系统开发和维护",
    "creator_id": "user_123",
    "member_count": 5,
    "create_time": "2025-01-01T10:00:00",
    "update_time": "2025-01-15T10:00:00"
  }
}
```

---

### Delete Team

**DELETE** `/api/v1/teams/{team_id}`

删除团队。

#### Request

- Method: DELETE
- URL: `/api/v1/teams/{team_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:5000/api/v1/teams/team_12345 \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "删除团队成功"
}
```

---

### Get Team Members

**GET** `/api/v1/teams/{team_id}/members`

获取团队成员列表。

#### Request

- Method: GET
- URL: `/api/v1/teams/{team_id}/members`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/teams/team_12345/members \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "members": [
      {
        "user_id": "user_123",
        "email": "user@example.com",
        "nickname": "开发者",
        "role": "admin",
        "join_time": "2025-01-01T10:00:00"
      }
    ],
    "total": 1
  }
}
```

---

### Remove Team Member

**DELETE** `/api/v1/teams/{team_id}/members/{user_id}`

从团队中移除成员。

#### Request

- Method: DELETE
- URL: `/api/v1/teams/{team_id}/members/{user_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:5000/api/v1/teams/team_12345/members/user_456 \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "移除团队成员成功"
}
```

---

## 租户管理 APIs

### List Tenants

**GET** `/api/v1/tenants`

获取租户列表。

#### Request

- Method: GET
- URL: `/api/v1/tenants`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/tenants \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "tenants": [
      {
        "id": "tenant_123",
        "name": "Default Tenant",
        "llm_id": "qwen-plus@Tongyi-Qianwen",
        "embd_id": "BAAI/bge-m3",
        "create_time": "2024-10-01T00:00:00",
        "update_time": "2025-01-01T00:00:00"
      }
    ],
    "total": 1
  }
}
```

---

### Get Available Models

**GET** `/api/v1/tenants/models`

获取可用的 LLM 和 Embedding 模型列表。

#### Request

- Method: GET
- URL: `/api/v1/tenants/models`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/tenants/models \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "llm_models": [
      {
        "model_name": "qwen-plus@Tongyi-Qianwen",
        "model_type": "chat",
        "provider": "Tongyi-Qianwen"
      },
      {
        "model_name": "gpt-4@OpenAI",
        "model_type": "chat",
        "provider": "OpenAI"
      }
    ],
    "embedding_models": [
      {
        "model_name": "BAAI/bge-m3",
        "dimensions": 1024,
        "provider": "HuggingFace"
      },
      {
        "model_name": "BAAI/bge-large-zh-v1.5",
        "dimensions": 1024,
        "provider": "HuggingFace"
      }
    ]
  }
}
```

---

### Get Admin Defaults

**GET** `/api/v1/tenants/admin-defaults`

获取管理员的默认配置。

#### Request

- Method: GET
- URL: `/api/v1/tenants/admin-defaults`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/tenants/admin-defaults \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "default_llm": "qwen-plus@Tongyi-Qianwen",
    "default_embedding": "BAAI/bge-m3",
    "default_chunk_method": "smart",
    "default_chunk_token_num": 256,
    "default_layout_recognize": "mineru"
  }
}
```

---

## 知识库管理 APIs

### List Knowledgebases

**GET** `/api/v1/knowledgebases`

获取知识库列表（根据用户权限筛选）。

#### Request

- Method: GET
- URL: `/api/v1/knowledgebases?current_page={page}&size={size}&name={name}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:5000/api/v1/knowledgebases?current_page=1&size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `current_page` (*Query parameter*) `integer`
  - 当前页码
  - Default: 1

- `size` (*Query parameter*) `integer`
  - 每页数量
  - Default: 10

- `name` (*Query parameter*) `string`
  - 按名称筛选（模糊匹配）

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "id": "4345aa0ea1a311f0b45566fc51ac58df",
        "name": "技术文档库",
        "description": "存储技术文档",
        "embedding_model": "BAAI/bge-m3",
        "chunk_method": "smart",
        "parser_config": {
          "layout_recognize": "mineru",
          "chunk_token_num": 256
        },
        "document_count": 10,
        "chunk_count": 245,
        "creator_id": "user_123",
        "create_time": "2025-01-01T00:00:00",
        "update_time": "2025-01-15T00:00:00"
      }
    ],
    "total": 1
  }
}
```

---

### Get Knowledgebase Details

**GET** `/api/v1/knowledgebases/{kb_id}`

获取知识库详细信息。

#### Request

- Method: GET
- URL: `/api/v1/knowledgebases/{kb_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "4345aa0ea1a311f0b45566fc51ac58df",
    "name": "技术文档库",
    "description": "存储技术文档",
    "embedding_model": "BAAI/bge-m3",
    "chunk_method": "smart",
    "parser_config": {
      "layout_recognize": "mineru",
      "chunk_token_num": 256,
      "min_chunk_tokens": 10
    },
    "document_count": 10,
    "chunk_count": 245,
    "creator_id": "user_123",
    "create_time": "2025-01-01T00:00:00",
    "update_time": "2025-01-15T00:00:00"
  }
}
```

---

### Create Knowledgebase

**POST** `/api/v1/knowledgebases`

创建新知识库。

#### Request

- Method: POST
- URL: `/api/v1/knowledgebases`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/knowledgebases \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "name": "新知识库",
       "description": "用于测试的知识库",
       "embedding_model": "BAAI/bge-m3",
       "chunk_method": "smart",
       "parser_config": {
         "layout_recognize": "mineru",
         "chunk_token_num": 256
       }
     }'
```

##### Request Parameters

- `name` (*Body parameter*) `string`, **Required**
  - 知识库名称
  - 必须唯一

- `description` (*Body parameter*) `string`
  - 知识库描述

- `embedding_model` (*Body parameter*) `string`
  - Embedding模型名称
  - 示例: `"BAAI/bge-m3"`

- `chunk_method` (*Body parameter*) `string`
  - 分块方法
  - 可选值: `"smart"`, `"naive"`, `"title"`, `"regex"`, `"parent_child"`
  - Default: `"smart"`

- `parser_config` (*Body parameter*) `object`
  - 解析配置
  - `layout_recognize` `string`: PDF解析器 (`"mineru"`, `"dots"`, `"deepdoc"`)
  - `chunk_token_num` `integer`: 分块大小 (1-2048)
  - `min_chunk_tokens` `integer`: 最小分块大小 (1-100)

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "kb_new123",
    "name": "新知识库",
    "create_time": "2025-01-17T10:00:00"
  },
  "message": "创建成功"
}
```

**Note**: 需要登录的用户session才能创建知识库（API Key不够）。

---

### Update Knowledgebase

**PUT** `/api/v1/knowledgebases/{kb_id}`

更新知识库信息。

#### Request

- Method: PUT
- URL: `/api/v1/knowledgebases/{kb_id}`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "description": "更新后的描述",
       "chunk_method": "naive"
     }'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "id": "4345aa0ea1a311f0b45566fc51ac58df",
    "updated": true
  }
}
```

---

### Delete Knowledgebase

**DELETE** `/api/v1/knowledgebases/{kb_id}`

删除知识库。

#### Request

- Method: DELETE
- URL: `/api/v1/knowledgebases/{kb_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:5000/api/v1/knowledgebases/kb_12345 \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "删除成功"
}
```

---

### Batch Delete Knowledgebases

**DELETE** `/api/v1/knowledgebases/batch`

批量删除知识库。

#### Request

- Method: DELETE
- URL: `/api/v1/knowledgebases/batch`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:5000/api/v1/knowledgebases/batch \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "kb_ids": ["kb_123", "kb_456"]
     }'
```

##### Request Parameters

- `kb_ids` (*Body parameter*) `array<string>`, **Required**
  - 知识库ID列表
  - 也支持 `kbIds` 或 `ids` 字段名

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "成功删除 2 个知识库"
}
```

---

### Get Knowledgebase Permissions

**GET** `/api/v1/knowledgebases/{kb_id}/permissions`

获取知识库的权限列表（用户和团队）。

#### Request

- Method: GET
- URL: `/api/v1/knowledgebases/{kb_id}/permissions`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df/permissions \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "users": [
      {
        "user_id": "user_123",
        "email": "user@example.com",
        "nickname": "开发者",
        "permission_level": "admin",
        "granted_at": "2025-01-01T00:00:00"
      }
    ],
    "teams": [
      {
        "team_id": "team_456",
        "team_name": "开发团队",
        "permission_level": "write",
        "granted_at": "2025-01-05T00:00:00"
      }
    ]
  }
}
```

---

### Grant User Permission

**POST** `/api/v1/knowledgebases/{kb_id}/permissions/users`

为用户授予知识库权限。

#### Request

- Method: POST
- URL: `/api/v1/knowledgebases/{kb_id}/permissions/users`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df/permissions/users \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "user_id": "user_123",
       "permission_level": "read"
     }'
```

##### Request Parameters

- `kb_id` (*Path parameter*) `string`, **Required**
  - 知识库ID

- `user_id` (*Body parameter*) `string`, **Required**
  - 用户ID

- `permission_level` (*Body parameter*) `string`, **Required**
  - 权限级别
  - 可选值:
    - `"admin"`: 管理权限（可修改、删除）
    - `"write"`: 写权限（可添加、编辑文档）
    - `"read"`: 读权限（仅查看）

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "message": "成功为用户授予read权限"
  },
  "message": "权限授予成功"
}
```

---

### Revoke User Permission

**DELETE** `/api/v1/knowledgebases/{kb_id}/permissions/users/{user_id}`

撤销用户的知识库权限。

#### Request

- Method: DELETE
- URL: `/api/v1/knowledgebases/{kb_id}/permissions/users/{user_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df/permissions/users/user_123 \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "message": "成功撤销3个权限"
  },
  "message": "权限撤销成功"
}
```

**Note**: 会撤销该用户在该知识库的所有权限级别（admin/write/read）。

---

### Check User Permission

**POST** `/api/v1/knowledgebases/{kb_id}/permissions/check`

检查用户对知识库的权限。

#### Request

- Method: POST
- URL: `/api/v1/knowledgebases/{kb_id}/permissions/check`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df/permissions/check \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "user_id": "user_123",
       "permission_type": "read"
     }'
```

##### Request Parameters

- `kb_id` (*Path parameter*) `string`, **Required**
  - 知识库ID

- `user_id` (*Body parameter*) `string`, **Required**
  - 用户ID

- `permission_type` (*Body parameter*) `string`
  - 权限类型
  - 可选值: `"read"`, `"write"`, `"delete"`
  - Default: `"read"`

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "has_permission": true,
    "user_id": "user_123",
    "resource_id": "4345aa0ea1a311f0b45566fc51ac58df",
    "permission_type": "read",
    "granted_roles": ["viewer"],
    "reason": "通过角色 viewer 授予"
  }
}
```

---

### Get Knowledgebase Documents

**GET** `/api/v1/knowledgebases/{kb_id}/documents`

获取知识库的文档列表。

#### Request

- Method: GET
- URL: `/api/v1/knowledgebases/{kb_id}/documents?current_page={page}&size={size}&name={name}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df/documents?current_page=1&size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `current_page` (*Query parameter*) `integer`
  - 当前页码
  - Default: 1

- `size` (*Query parameter*) `integer`
  - 每页数量
  - Default: 10

- `name` (*Query parameter*) `string`
  - 按文档名筛选（模糊匹配）

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "id": "c6db195ea4b811f097ee66fc51ac58df",
        "name": "技术文档.pdf",
        "size": 1024567,
        "type": "pdf",
        "status": "1",
        "progress": 100,
        "chunk_count": 45,
        "parser_id": "smart",
        "parser_config": {
          "layout_recognize": "mineru",
          "chunk_token_num": 256
        },
        "create_time": "2025-01-10T00:00:00",
        "update_time": "2025-01-10T01:00:00"
      }
    ],
    "total": 1
  }
}
```

---

### Add Documents to Knowledgebase

**POST** `/api/v1/knowledgebases/{kb_id}/documents`

将已上传的文件添加到知识库。

#### Request

- Method: POST
- URL: `/api/v1/knowledgebases/{kb_id}/documents`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df/documents \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "file_ids": ["file_123", "file_456"]
     }'
```

##### Request Parameters

- `kb_id` (*Path parameter*) `string`, **Required**
  - 知识库ID

- `file_ids` (*Body parameter*) `array<string>`, **Required**
  - 文件ID列表（通过文件上传API获得）

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "added_count": 2,
    "documents": [
      {
        "id": "doc_789",
        "name": "文档1.pdf",
        "file_id": "file_123"
      },
      {
        "id": "doc_790",
        "name": "文档2.pdf",
        "file_id": "file_456"
      }
    ]
  },
  "message": "添加成功"
}
```

---

### Delete Document

**DELETE** `/api/v1/knowledgebases/documents/{doc_id}`

删除文档。

#### Request

- Method: DELETE
- URL: `/api/v1/knowledgebases/documents/{doc_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:5000/api/v1/knowledgebases/documents/doc_123 \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "删除成功"
}
```

---

### Update Document Parser Config

**POST** `/api/v1/knowledgebases/documents/{doc_id}/update-parser-config`

更新文档的解析配置（不触发重新解析）。

#### Request

- Method: POST
- URL: `/api/v1/knowledgebases/documents/{doc_id}/update-parser-config`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/knowledgebases/documents/doc_123/update-parser-config \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "parser_id": "smart",
       "layout_recognize": "mineru",
       "parser_config": {
         "chunk_token_num": 512
       }
     }'
```

##### Request Parameters

- `doc_id` (*Path parameter*) `string`, **Required**
  - 文档ID

- `parser_id` (*Body parameter*) `string`
  - 分块方法
  - 可选值: `"smart"`, `"naive"`, `"title"`, etc.

- `layout_recognize` (*Body parameter*) `string`
  - PDF解析器
  - 可选值: `"mineru"`, `"dots"`, `"deepdoc"`

- `parser_config` (*Body parameter*) `object`
  - 其他解析配置
  - `chunk_token_num` `integer`: 分块大小

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "success": true,
    "doc_id": "doc_123"
  },
  "message": "配置已保存"
}
```

---

### Parse Document

**POST** `/api/v1/knowledgebases/documents/{doc_id}/parse`

开始解析文档。

#### Request

- Method: POST
- URL: `/api/v1/knowledgebases/documents/{doc_id}/parse`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>` (RAGFlow API Key)

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/knowledgebases/documents/doc_123/parse \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "parser_id": "smart",
       "layout_recognize": "mineru"
     }'
```

##### Request Parameters

- `doc_id` (*Path parameter*) `string`, **Required**
  - 文档ID

- `parser_id` (*Body parameter*) `string`
  - 临时覆盖分块方法（不修改文档配置）

- `layout_recognize` (*Body parameter*) `string`
  - 临时覆盖PDF解析器

- `parser_config` (*Body parameter*) `object`
  - 临时覆盖其他配置

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "success": true,
    "doc_id": "doc_123",
    "task_id": "task_789",
    "status": "parsing"
  }
}
```

**Note**:
- 需要用户对知识库有写权限
- 解析过程异步执行，需要轮询进度接口

---

### Get Parse Progress

**GET** `/api/v1/knowledgebases/documents/{doc_id}/parse/progress`

获取文档解析进度。

#### Request

- Method: GET
- URL: `/api/v1/knowledgebases/documents/{doc_id}/parse/progress`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/knowledgebases/documents/doc_123/parse/progress \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success - Parsing (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "status": "parsing",
    "progress": 45.5,
    "progress_msg": "正在解析第10页...",
    "doc_id": "doc_123",
    "task_id": "task_789"
  }
}
```

Success - Completed (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "status": "completed",
    "progress": 100,
    "progress_msg": "解析完成",
    "doc_id": "doc_123",
    "chunk_count": 45
  }
}
```

**Status Values**:
- `"pending"`: 等待解析
- `"parsing"`: 解析中
- `"completed"`: 解析完成
- `"failed"`: 解析失败

---

### Cancel Parse

**POST** `/api/v1/knowledgebases/documents/{doc_id}/parse/cancel`

取消文档解析。

#### Request

- Method: POST
- URL: `/api/v1/knowledgebases/documents/{doc_id}/parse/cancel`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/knowledgebases/documents/doc_123/parse/cancel \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "success": true,
    "doc_id": "doc_123"
  },
  "message": "取消解析成功"
}
```

---

### Start Batch Parse

**POST** `/api/v1/knowledgebases/{kb_id}/batch_parse/start`

启动知识库的批量文档解析。

#### Request

- Method: POST
- URL: `/api/v1/knowledgebases/{kb_id}/batch_parse/start`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df/batch_parse/start \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "success": true,
    "kb_id": "4345aa0ea1a311f0b45566fc51ac58df",
    "total_documents": 10,
    "status": "started"
  }
}
```

---

### Get Batch Parse Progress

**GET** `/api/v1/knowledgebases/{kb_id}/batch_parse/progress`

获取批量解析进度。

#### Request

- Method: GET
- URL: `/api/v1/knowledgebases/{kb_id}/batch_parse/progress`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/knowledgebases/4345aa0ea1a311f0b45566fc51ac58df/batch_parse/progress \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "kb_id": "4345aa0ea1a311f0b45566fc51ac58df",
    "total_documents": 10,
    "completed": 7,
    "failed": 1,
    "parsing": 2,
    "progress_percentage": 70.0,
    "documents": [
      {
        "doc_id": "doc_123",
        "name": "文档1.pdf",
        "status": "completed",
        "progress": 100
      },
      {
        "doc_id": "doc_456",
        "name": "文档2.pdf",
        "status": "parsing",
        "progress": 45
      }
    ]
  }
}
```

---

### Get System Embedding Config

**GET** `/api/v1/knowledgebases/system_embedding_config`

获取系统级的 Embedding 配置。

#### Request

- Method: GET
- URL: `/api/v1/knowledgebases/system_embedding_config`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/knowledgebases/system_embedding_config \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "llm_name": "BAAI/bge-m3",
    "api_base": "http://localhost:8000",
    "api_key": "sk-xxxxx"
  }
}
```

---

### Set System Embedding Config

**POST** `/api/v1/knowledgebases/system_embedding_config`

设置系统级的 Embedding 配置。

#### Request

- Method: POST
- URL: `/api/v1/knowledgebases/system_embedding_config`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/knowledgebases/system_embedding_config \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "llm_name": "BAAI/bge-m3",
       "api_base": "http://localhost:8000",
       "api_key": "sk-xxxxx"
     }'
```

##### Request Parameters

- `llm_name` (*Body parameter*) `string`, **Required**
  - Embedding模型名称

- `api_base` (*Body parameter*) `string`, **Required**
  - API基础URL

- `api_key` (*Body parameter*) `string`
  - API密钥（可选）

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "Embedding配置保存成功"
}
```

---

## 文档管理 APIs

### Get Document Chunking Config

**GET** `/api/v1/documents/{doc_id}/chunking-config`

获取文档的父子分块配置。

#### Request

- Method: GET
- URL: `/api/v1/documents/{doc_id}/chunking-config`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/documents/c6db195ea4b811f097ee66fc51ac58df/chunking-config \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "doc_id": "c6db195ea4b811f097ee66fc51ac58df",
    "chunk_method": "smart",
    "use_parent_child": true,
    "child_chunk_size": 256,
    "parent_chunk_size": 1024,
    "overlap": 50
  }
}
```

---

### Update Document Chunking Config

**PUT** `/api/v1/documents/{doc_id}/chunking-config`

更新文档的父子分块配置。

#### Request

- Method: PUT
- URL: `/api/v1/documents/{doc_id}/chunking-config`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request PUT \
     --url http://localhost:5000/api/v1/documents/c6db195ea4b811f097ee66fc51ac58df/chunking-config \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "chunk_method": "smart",
       "chunk_token_num": 512,
       "use_parent_child": true
     }'
```

##### Request Parameters

- `doc_id` (*Path parameter*) `string`, **Required**
  - 文档ID

- `chunk_method` (*Body parameter*) `string`
  - 分块方法

- `chunk_token_num` (*Body parameter*) `integer`
  - 子块大小（如果使用父子分块）

- `use_parent_child` (*Body parameter*) `boolean`
  - 是否启用父子分块
  - Default: `false`

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "分块配置已更新"
}
```

---

## 文件管理 APIs

### Upload File

**POST** `/api/v1/files/upload`

上传文件到系统（未关联知识库）。

#### Request

- Method: POST
- URL: `/api/v1/files/upload`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`
  - **Note**: 文件上传不设置 `Content-Type`（自动为 multipart/form-data）

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/files/upload \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --form 'file=@/path/to/document.pdf'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": [
    {
      "id": "file_12345",
      "name": "document.pdf",
      "size": 1024567,
      "type": "application/pdf",
      "upload_time": "2025-01-17T10:00:00"
    }
  ],
  "message": "文件上传成功"
}
```

**Note**: 上传的文件需要通过 "Add Documents to Knowledgebase" API 添加到知识库。

---

### List Files

**GET** `/api/v1/files`

获取已上传的文件列表。

#### Request

- Method: GET
- URL: `/api/v1/files?current_page={page}&size={size}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:5000/api/v1/files?current_page=1&size=10' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `current_page` (*Query parameter*) `integer`
  - 当前页码
  - Default: 1

- `size` (*Query parameter*) `integer`
  - 每页数量
  - Default: 10

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "data": {
    "list": [
      {
        "id": "file_12345",
        "name": "document.pdf",
        "size": 1024567,
        "type": "application/pdf",
        "upload_time": "2025-01-17T10:00:00",
        "is_used": false
      }
    ],
    "total": 1
  }
}
```

---

### Download File

**GET** `/api/v1/files/{file_id}/download`

下载文件。

#### Request

- Method: GET
- URL: `/api/v1/files/{file_id}/download`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/files/file_12345/download \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --output document.pdf
```

#### Response

Success (HTTP 200): 返回文件二进制流

---

### Delete File

**DELETE** `/api/v1/files/{file_id}`

删除单个文件。

#### Request

- Method: DELETE
- URL: `/api/v1/files/{file_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:5000/api/v1/files/file_12345 \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "文件删除成功"
}
```

---

### Batch Delete Files

**DELETE** `/api/v1/files/batch`

批量删除文件。

#### Request

- Method: DELETE
- URL: `/api/v1/files/batch`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request DELETE \
     --url http://localhost:5000/api/v1/files/batch \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "file_ids": ["file_123", "file_456"]
     }'
```

##### Request Parameters

- `file_ids` (*Body parameter*) `array<string>`, **Required**
  - 文件ID列表

#### Response

Success (HTTP 200):

```json
{
  "code": 0,
  "message": "成功删除 2 个文件"
}
```

---

## RBAC权限管理 APIs

### RBAC Health Check

**GET** `/api/v1/rbac/health`

检查 RBAC 系统健康状态。

#### Request

- Method: GET
- URL: `/api/v1/rbac/health`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/rbac/health \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "service": "RBAC权限管理系统",
  "status": "healthy",
  "timestamp": "2025-01-17T00:00:00",
  "version": "1.0.0"
}
```

---

### List Roles

**GET** `/api/v1/rbac/roles`

获取所有角色列表。

#### Request

- Method: GET
- URL: `/api/v1/rbac/roles`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/rbac/roles \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "data": [
    {
      "id": 1,
      "code": "super_admin",
      "name": "超级管理员",
      "description": "系统超级管理员，拥有所有权限",
      "is_system": true,
      "created_at": "2025-01-01T00:00:00"
    },
    {
      "id": 2,
      "code": "admin",
      "name": "管理员",
      "description": "可以管理资源",
      "is_system": true,
      "created_at": "2025-01-01T00:00:00"
    },
    {
      "id": 3,
      "code": "editor",
      "name": "编辑者",
      "description": "可以编辑资源",
      "is_system": true,
      "created_at": "2025-01-01T00:00:00"
    },
    {
      "id": 4,
      "code": "viewer",
      "name": "查看者",
      "description": "只能查看资源",
      "is_system": true,
      "created_at": "2025-01-01T00:00:00"
    }
  ]
}
```

---

### Get Assignable Roles

**GET** `/api/v1/rbac/assignable-roles`

获取当前用户可以分配的角色列表。

#### Request

- Method: GET
- URL: `/api/v1/rbac/assignable-roles`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/rbac/assignable-roles \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
{
  "data": [
    {
      "code": "admin",
      "name": "管理员",
      "description": "可以管理资源"
    },
    {
      "code": "editor",
      "name": "编辑者",
      "description": "可以编辑资源"
    },
    {
      "code": "viewer",
      "name": "查看者",
      "description": "只能查看资源"
    }
  ]
}
```

**Note**: 超级管理员角色通常不在可分配列表中。

---

### Get My Roles

**GET** `/api/v1/rbac/my/roles`

获取当前用户的角色列表。

#### Request

- Method: GET
- URL: `/api/v1/rbac/my/roles?user_id={user_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:5000/api/v1/rbac/my/roles?user_id=user_123' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `user_id` (*Query parameter*) `string`, **Required**
  - 用户ID（通常从token中解析）

#### Response

Success (HTTP 200):

```json
{
  "user_id": "user_123",
  "roles": [
    {
      "role_code": "admin",
      "resource_type": null,
      "resource_id": null,
      "tenant_id": "default",
      "is_active": true
    }
  ]
}
```

---

### Get My Permissions

**GET** `/api/v1/rbac/my/permissions`

获取当前用户的权限列表。

#### Request

- Method: GET
- URL: `/api/v1/rbac/my/permissions?user_id={user_id}`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url 'http://localhost:5000/api/v1/rbac/my/permissions?user_id=user_123' \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

##### Query Parameters

- `user_id` (*Query parameter*) `string`, **Required**
  - 用户ID

#### Response

Success (HTTP 200):

```json
{
  "user_id": "user_123",
  "permissions": [
    {
      "permission_code": "kb:read",
      "permission_name": "查看知识库",
      "resource_type": "knowledgebase",
      "description": "可以查看知识库内容"
    },
    {
      "permission_code": "kb:write",
      "permission_name": "编辑知识库",
      "resource_type": "knowledgebase",
      "description": "可以编辑知识库"
    }
  ]
}
```

---

### List Permissions

**GET** `/api/v1/rbac/permissions`

获取所有权限列表。

#### Request

- Method: GET
- URL: `/api/v1/rbac/permissions`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/rbac/permissions \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
[
  {
    "id": 1,
    "code": "kb:read",
    "name": "查看知识库",
    "resource_type": "knowledgebase",
    "description": "可以查看知识库内容"
  },
  {
    "id": 2,
    "code": "kb:write",
    "name": "编辑知识库",
    "resource_type": "knowledgebase",
    "description": "可以编辑知识库"
  }
]
```

---

### Get Role Permissions

**GET** `/api/v1/rbac/roles/{role_code}/permissions`

获取指定角色的权限列表。

#### Request

- Method: GET
- URL: `/api/v1/rbac/roles/{role_code}/permissions`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request GET \
     --url http://localhost:5000/api/v1/rbac/roles/admin/permissions \
     --header 'Authorization: Bearer <YOUR_API_KEY>'
```

#### Response

Success (HTTP 200):

```json
[
  {
    "permission_code": "kb:read",
    "permission_name": "查看知识库",
    "resource_type": "knowledgebase"
  },
  {
    "permission_code": "kb:write",
    "permission_name": "编辑知识库",
    "resource_type": "knowledgebase"
  },
  {
    "permission_code": "kb:delete",
    "permission_name": "删除知识库",
    "resource_type": "knowledgebase"
  }
]
```

---

### Check Permission

**POST** `/api/v1/rbac/permissions/check`

检查用户是否有指定权限。

#### Request

- Method: POST
- URL: `/api/v1/rbac/permissions/check`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/rbac/permissions/check \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "user_id": "user_123",
       "resource_type": "knowledgebase",
       "resource_id": "kb_456",
       "permission_type": "read",
       "tenant_id": "default"
     }'
```

##### Request Parameters

- `user_id` (*Body parameter*) `string`, **Required**
  - 用户ID

- `resource_type` (*Body parameter*) `string`, **Required**
  - 资源类型
  - 可选值: `"knowledgebase"`, `"document"`, `"team"`

- `resource_id` (*Body parameter*) `string`, **Required**
  - 资源ID

- `permission_type` (*Body parameter*) `string`, **Required**
  - 权限类型
  - 可选值: `"read"`, `"write"`, `"delete"`

- `tenant_id` (*Body parameter*) `string`
  - 租户ID
  - Default: `"default"`

#### Response

Success (HTTP 200):

```json
{
  "has_permission": true,
  "user_id": "user_123",
  "resource_id": "kb_456",
  "resource_type": "knowledgebase",
  "permission_type": "read",
  "granted_roles": ["admin"],
  "reason": "通过角色 admin 授予"
}
```

---

### Batch Check Permissions

**POST** `/api/v1/rbac/permissions/batch-check`

批量检查权限。

#### Request

- Method: POST
- URL: `/api/v1/rbac/permissions/batch-check`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/v1/rbac/permissions/batch-check \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "user_id": "user_123",
       "checks": [
         {
           "resource_type": "knowledgebase",
           "resource_id": "kb_456",
           "permission_type": "read"
         },
         {
           "resource_type": "knowledgebase",
           "resource_id": "kb_789",
           "permission_type": "write"
         }
       ]
     }'
```

#### Response

Success (HTTP 200):

```json
{
  "user_id": "user_123",
  "results": [
    {
      "resource_id": "kb_456",
      "permission_type": "read",
      "has_permission": true
    },
    {
      "resource_id": "kb_789",
      "permission_type": "write",
      "has_permission": false
    }
  ]
}
```

---

## 文档解析服务 APIs

### Parse with MinerU

**POST** `/api/parse/mineru`

使用 MinerU 解析 PDF 文档。

#### Request

- Method: POST
- URL: `/api/parse/mineru`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/parse/mineru \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --form 'file=@/path/to/document.pdf' \
     --form 'from_page=0' \
     --form 'to_page=10' \
     --form 'kb_id=kb_12345'
```

##### Request Parameters

- `file` (*Form parameter*) `file`, **Required**
  - PDF文件

- `from_page` (*Form parameter*) `integer`
  - 起始页码（0-based）
  - Default: 0

- `to_page` (*Form parameter*) `integer`
  - 结束页码
  - Default: 100000

- `kb_id` (*Form parameter*) `string`
  - 知识库ID（用于保存解析图片）

#### Response

Success (HTTP 200):

```json
{
  "success": true,
  "boxes": [
    {
      "text": "第一章 引言",
      "x0": 100,
      "x1": 500,
      "top": 50,
      "bottom": 100,
      "page_number": 0,
      "layout_type": "title"
    },
    {
      "text": "这是正文内容...",
      "x0": 100,
      "x1": 500,
      "top": 150,
      "bottom": 200,
      "page_number": 0,
      "layout_type": "text"
    }
  ],
  "markdown": "# 第一章 引言\n\n这是正文内容...",
  "coordinate_map": {
    "0": [0, 100, 500, 50, 100],
    "2": [0, 100, 500, 150, 200]
  },
  "page_count": 5,
  "total_blocks": 150
}
```

**Response Fields**:
- `boxes`: 语义块级别的结构化数据（用于 general 分块）
- `markdown`: 完整的 markdown 文本（用于 smart 分块）
- `coordinate_map`: 坐标映射 `{line_idx: [page, x0, x1, y0, y1]}`
- `page_count`: 解析的页数
- `total_blocks`: 总块数

**Layout Types**:
- `"title"`: 标题
- `"text"`: 正文
- `"table"`: 表格
- `"image"`: 图片
- `"list"`: 列表

---

### Parse with DOTS

**POST** `/api/parse/dots`

使用 DOTS 解析 PDF 文档。

#### Request

- Method: POST
- URL: `/api/parse/dots`
- Headers:
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/parse/dots \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --form 'file=@/path/to/document.pdf' \
     --form 'from_page=0' \
     --form 'to_page=10' \
     --form 'kb_id=kb_12345'
```

##### Request Parameters

Same as MinerU Parse API.

#### Response

Success (HTTP 200):

Same format as MinerU Parse API.

**Note**: DOTS 解析速度更快，但精度略低于 MinerU。

---

### Smart Chunk

**POST** `/api/parse/smart_chunk`

智能分块服务：基于 markdown 文本和坐标映射进行智能分块。

#### Request

- Method: POST
- URL: `/api/parse/smart_chunk`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer <YOUR_API_KEY>`

##### Request Example

```bash
curl --request POST \
     --url http://localhost:5000/api/parse/smart_chunk \
     --header 'Content-Type: application/json' \
     --header 'Authorization: Bearer <YOUR_API_KEY>' \
     --data '{
       "markdown": "# Title\n\nParagraph 1\n\n## Subtitle\n\nParagraph 2",
       "coordinate_map": {
         "0": [0, 100, 200, 50, 100],
         "2": [0, 100, 200, 150, 200],
         "4": [0, 100, 200, 250, 300],
         "6": [0, 100, 200, 350, 400]
       },
       "chunk_token_num": 256,
       "min_chunk_tokens": 10
     }'
```

##### Request Parameters

- `markdown` (*Body parameter*) `string`, **Required**
  - Markdown 格式的文档文本

- `coordinate_map` (*Body parameter*) `object`, **Required**
  - 坐标映射 `{line_idx: [page, x0, x1, y0, y1]}`

- `chunk_token_num` (*Body parameter*) `integer`
  - 目标分块大小（token数）
  - Default: 256
  - Range: 1-2048

- `min_chunk_tokens` (*Body parameter*) `integer`
  - 最小分块大小
  - Default: 10
  - Range: 1-100

#### Response

Success (HTTP 200):

```json
{
  "success": true,
  "chunks": [
    {
      "text": "# Title\n\nParagraph 1",
      "token_count": 45,
      "coordinates": [0, 100, 200, 50, 200],
      "page_number": 0
    },
    {
      "text": "## Subtitle\n\nParagraph 2",
      "token_count": 38,
      "coordinates": [0, 100, 200, 250, 400],
      "page_number": 0
    }
  ],
  "total_chunks": 2,
  "total_tokens": 83
}
```

**Chunking Strategy**:
1. 基于 markdown 结构（标题层级）
2. 保持语义完整性
3. 控制分块大小在目标范围内
4. 保留坐标映射信息

---

## 代码示例

### Python: 完整工作流

```python
import requests
import json
import time

BASE_URL = "http://localhost:5000"
API_KEY = "ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 1. 检查系统健康状态
response = requests.get(f"{BASE_URL}/health")
print(f"System Health: {response.json()['data']['status']}")

# 2. 获取当前用户信息（需要RAGFlow API Key）
response = requests.get(f"{BASE_URL}/api/v1/users/me", headers=headers)
if response.status_code == 200:
    user = response.json()['data']
    print(f"Current User: {user['email']}, Role: {user['role']}")

# 3. 创建用户
new_user_data = {
    "email": "newuser@example.com",
    "password": "SecurePass@123",
    "nickname": "New User"
}
response = requests.post(
    f"{BASE_URL}/api/v1/users",
    headers=headers,
    json=new_user_data
)
# Note: 需要登录session，API Key不够

# 4. 创建团队
team_data = {
    "name": "Development Team",
    "description": "Core development team"
}
response = requests.post(
    f"{BASE_URL}/api/v1/teams",
    headers=headers,
    json=team_data
)
# Note: 需要登录session

# 5. 获取知识库列表
response = requests.get(
    f"{BASE_URL}/api/v1/knowledgebases",
    headers=headers,
    params={"current_page": 1, "size": 10}
)
kbs = response.json()['data']['list']
print(f"Found {len(kbs)} knowledge bases")

# 6. 上传文件
with open("document.pdf", "rb") as f:
    files = {"file": ("document.pdf", f, "application/pdf")}
    headers_upload = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.post(
        f"{BASE_URL}/api/v1/files/upload",
        headers=headers_upload,
        files=files
    )
    file_id = response.json()['data'][0]['id']
    print(f"Uploaded File ID: {file_id}")

# 7. 添加文件到知识库
kb_id = "4345aa0ea1a311f0b45566fc51ac58df"
add_docs_data = {
    "file_ids": [file_id]
}
response = requests.post(
    f"{BASE_URL}/api/v1/knowledgebases/{kb_id}/documents",
    headers=headers,
    json=add_docs_data
)
doc_id = response.json()['data']['documents'][0]['id']
print(f"Document ID: {doc_id}")

# 8. 开始解析文档
parse_data = {
    "parser_id": "smart",
    "layout_recognize": "mineru"
}
response = requests.post(
    f"{BASE_URL}/api/v1/knowledgebases/documents/{doc_id}/parse",
    headers=headers,
    json=parse_data
)
print("Parse started")

# 9. 轮询解析进度
while True:
    response = requests.get(
        f"{BASE_URL}/api/v1/knowledgebases/documents/{doc_id}/parse/progress",
        headers=headers
    )
    progress = response.json()['data']
    status = progress['status']
    print(f"Parse Status: {status}, Progress: {progress.get('progress', 0)}%")

    if status == "completed":
        print("Parse completed!")
        break
    elif status == "failed":
        print("Parse failed!")
        break

    time.sleep(5)

# 10. 授予用户权限
user_id = "user_123"
grant_data = {
    "user_id": user_id,
    "permission_level": "read"
}
response = requests.post(
    f"{BASE_URL}/api/v1/knowledgebases/{kb_id}/permissions/users",
    headers=headers,
    json=grant_data
)
print(f"Permission granted to user {user_id}")

# 11. 检查权限
check_data = {
    "user_id": user_id,
    "permission_type": "read"
}
response = requests.post(
    f"{BASE_URL}/api/v1/knowledgebases/{kb_id}/permissions/check",
    headers=headers,
    json=check_data
)
has_perm = response.json()['data']['has_permission']
print(f"User has read permission: {has_perm}")
```

---

### Python: MinerU 解析示例

```python
import requests

BASE_URL = "http://localhost:5000"
API_KEY = "ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh"

# 使用 MinerU 解析 PDF
with open("document.pdf", "rb") as f:
    files = {"file": ("document.pdf", f, "application/pdf")}
    form_data = {
        "from_page": "0",
        "to_page": "10",
        "kb_id": "kb_12345"
    }
    headers = {"Authorization": f"Bearer {API_KEY}"}

    response = requests.post(
        f"{BASE_URL}/api/parse/mineru",
        headers=headers,
        data=form_data,
        files=files
    )

    result = response.json()

    if result['success']:
        print(f"Parsed {result['page_count']} pages")
        print(f"Total blocks: {result['total_blocks']}")

        # 获取 markdown
        markdown = result['markdown']
        print(f"Markdown length: {len(markdown)}")

        # 获取结构化boxes
        boxes = result['boxes']
        for box in boxes[:5]:  # 前5个块
            print(f"Page {box['page_number']}: [{box['layout_type']}] {box['text'][:50]}...")
```

---

### Python: 智能分块示例

```python
import requests
import json

BASE_URL = "http://localhost:5000"
API_KEY = "ragflow-NThkYWEwMTkzODM2NDYwN2ExY2I2MzFh"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 智能分块
chunk_data = {
    "markdown": """# 机器学习简介

机器学习是人工智能的一个分支，它使计算机能够在没有明确编程的情况下学习。

## 监督学习

监督学习是一种机器学习方法，其中模型从标记的训练数据中学习。

## 无监督学习

无监督学习是在没有预先存在标签的情况下对数据进行训练。""",
    "coordinate_map": {
        "0": [0, 100, 500, 50, 100],
        "2": [0, 100, 500, 150, 200],
        "4": [0, 100, 500, 250, 300],
        "6": [0, 100, 500, 350, 400],
        "8": [0, 100, 500, 450, 500]
    },
    "chunk_token_num": 256,
    "min_chunk_tokens": 10
}

response = requests.post(
    f"{BASE_URL}/api/parse/smart_chunk",
    headers=headers,
    json=chunk_data
)

result = response.json()

if result['success']:
    print(f"Total chunks: {result['total_chunks']}")
    print(f"Total tokens: {result['total_tokens']}")

    for i, chunk in enumerate(result['chunks']):
        print(f"\n--- Chunk {i+1} ---")
        print(f"Tokens: {chunk['token_count']}")
        print(f"Page: {chunk['page_number']}")
        print(f"Text: {chunk['text'][:100]}...")
```

---

## 最佳实践

### 1. 认证方式选择

**API Key 认证** (推荐用于程序化访问):
- 从 RAGFlow 获取 API Key
- 长期有效，适合自动化脚本
- 权限与创建 API Key 的用户相同

**JWT Token 认证** (用于 Web 管理界面):
- 通过登录接口获取
- 有过期时间，需要定期刷新
- 用于前端管理界面

### 2. 权限管理

**角色层级**:
```
super_admin (超级管理员)
  ↓
admin (管理员)
  ↓
editor (编辑者)
  ↓
viewer (查看者)
  ↓
user (普通用户)
```

**最小权限原则**:
- 只授予必要的权限级别
- 使用资源级角色而不是全局角色
- 定期审查和撤销不需要的权限

### 3. 文档解析选择

**MinerU** - 高精度:
- 适用于：复杂PDF、学术论文、多栏布局
- 特点：精度高、速度较慢
- 配置：`{"layout_recognize": "mineru"}`

**DOTS** - 高速度:
- 适用于：简单PDF、标准格式文档
- 特点：速度快、精度略低
- 配置：`{"layout_recognize": "dots"}`

**DeepDOC** - 平衡:
- 适用于：一般文档
- 特点：速度和精度平衡
- 配置：`{"layout_recognize": "deepdoc"}`

### 4. 分块策略

**Smart Chunking** (推荐):
- 基于文档结构智能分块
- 保持语义完整性
- 适合大多数场景

**Parent-Child Chunking**:
- 子块用于精确检索
- 父块提供上下文
- 适合需要上下文的场景

**配置建议**:
```json
{
  "chunk_method": "smart",
  "chunk_token_num": 256,
  "min_chunk_tokens": 10,
  "layout_recognize": "mineru"
}
```

### 5. 批量操作

**批量解析文档**:
- 使用 `/batch_parse/start` 接口
- 轮询 `/batch_parse/progress` 获取进度
- 失败的文档单独重试

**批量权限管理**:
- 使用批量权限检查 API
- 减少 API 调用次数
- 提高性能

### 6. 错误处理

```python
try:
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()

    if result.get("code") != 0:
        print(f"API Error: {result.get('message')}")
        # 根据错误码处理
        if result.get("code") == 109:
            print("Permission denied - check user permissions")
        elif result.get("code") == 401:
            print("Unauthorized - check API key")
    else:
        # 处理成功响应
        data = result.get("data")

except requests.exceptions.Timeout:
    print("Request timeout - retry later")
except requests.exceptions.ConnectionError:
    print("Connection error - check service status")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## 测试结果总结

基于测试脚本执行结果 (scripts/knowflow_server_api_test_results.json):

### 测试统计

- **总计测试**: 41 个 API
- **成功**: 21 个 (51.2%)
- **失败**: 20 个 (48.8%)

### 按分类成功率

| 分类 | 成功率 | 备注 |
|------|--------|------|
| Authentication | 100% (2/2) | ✅ 全部通过 |
| Tenant Management | 100% (3/3) | ✅ 全部通过 |
| Knowledgebase Management | 90% (9/10) | ✅ 核心功能正常 |
| User Management | 55.6% (5/9) | ⚠️ 需要登录session |
| Document Management | 50% (1/2) | ⚠️ 配置参数问题 |
| Team Management | 50% (1/2) | ⚠️ 需要登录session |
| RBAC Management | 0% (0/12) | ❌ 响应格式问题 |
| File Management | 0% (0/1) | ❌ 需要登录session |

### 主要问题

1. **认证限制**: 很多创建操作需要登录 session，API Key 不够
2. **RBAC API**: 响应格式与预期不同（返回列表而非对象）
3. **测试文件**: 测试 PDF 文件不存在，无法测试解析功能

### 建议

1. 使用 RAGFlow Web 界面登录获取 JWT Token 进行完整测试
2. RBAC API 响应格式需要适配（已知问题）
3. 准备测试文件用于解析服务测试

---

**注意**: 本文档基于实际API测试结果编写。部分API需要特定权限或登录session才能完全测试。

---

**支持与反馈**

- GitHub Issues: https://github.com/your-repo/knowflow/issues
- 文档: https://docs.knowflow.ai
- Email: support@knowflow.ai
