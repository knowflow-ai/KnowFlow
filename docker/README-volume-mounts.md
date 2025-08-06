# Docker 文件挂载配置说明

## 概述
在 `docker-compose.yml` 中配置了 KnowFlow API 文件的挂载，这些文件会被挂载到 `ragflow-server` 容器内部，用于覆盖容器内的默认文件。

## 挂载的文件

### 1. document_app.py
- **源路径**: `../api/apps/document_app.py`
- **容器路径**: `/ragflow/api/apps/document_app.py`
- **作用**: 文档处理应用的主要逻辑文件
- **权限**: 只读 (`:ro`)

### 2. db_models.py
- **源路径**: `../api/db/db_models.py`
- **容器路径**: `/ragflow/api/db/db_models.py`
- **作用**: 数据库模型定义文件
- **权限**: 只读 (`:ro`)

### 3. doc.py
- **源路径**: `../api/apps/sdk/doc.py`
- **容器路径**: `/ragflow/api/apps/sdk/doc.py`
- **作用**: SDK文档处理相关功能
- **权限**: 只读 (`:ro`)

## 配置说明

```yaml
volumes:
  # 挂载KnowFlow API文件到容器内部
  - ../api/apps/document_app.py:/ragflow/api/apps/document_app.py:ro
  - ../api/db/db_models.py:/ragflow/api/db/db_models.py:ro
  - ../api/apps/sdk/doc.py:/ragflow/api/apps/sdk/doc.py:ro
```

## 使用场景

1. **开发调试**: 在开发过程中，可以修改容器外的文件，修改会立即反映到容器内
2. **自定义功能**: 可以覆盖容器内的默认实现，添加自定义功能
3. **热更新**: 修改文件后重启容器即可生效，无需重新构建镜像

## 注意事项

1. **文件权限**: 所有挂载的文件都设置为只读 (`:ro`)，防止容器内意外修改
2. **路径映射**: 确保源文件路径正确，相对于 docker-compose.yml 文件的位置
3. **容器重启**: 修改挂载的文件后需要重启容器才能生效
4. **备份建议**: 在修改重要文件前建议先备份

## 重启容器

修改挂载的文件后，需要重启容器：

```bash
# 重启 ragflow-server 容器
docker-compose restart ragflow

# 或者重新启动整个服务
docker-compose down && docker-compose up -d
```

## 验证挂载

可以通过以下命令验证文件是否正确挂载：

```bash
# 进入容器
docker exec -it ragflow-server bash

# 检查文件是否存在
ls -la /ragflow/api/apps/document_app.py
ls -la /ragflow/api/db/db_models.py
ls -la /ragflow/api/apps/sdk/doc.py
``` 