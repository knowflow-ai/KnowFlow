    #
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import logging
import os
import re

from flask import request, jsonify

from api.db import LLMType
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.llm_service import LLMBundle
from api import settings
from api.utils.api_utils import validate_request, build_error_result, apikey_required
from rag.app.tag import label_question
from api.db.services.dialog_service import meta_filter, convert_conditions


def _get_minio_external_url():
    """
    获取 MinIO 外部访问地址

    Returns:
        str: MinIO 外部访问 URL，从环境变量 MINIO_EXTERNAL_URL 读取
    """
    return os.getenv('MINIO_EXTERNAL_URL', 'http://localhost:9000')


def _replace_minio_urls_to_external(content: str, minio_url: str) -> str:
    """
    将内容中的 MinIO 相对路径替换为外部可访问的绝对路径

    Args:
        content: 包含图片路径的内容（HTML/Markdown）
        minio_url: MinIO 外部访问 URL (如 http://192.168.1.100:9000)

    Returns:
        str: 替换后的内容

    Examples:
        输入: <img src="/minio/kb123/abc.jpg">
        输出: <img src="http://192.168.1.100:9000/kb123/abc.jpg">
    """
    if not content:
        return content

    # 匹配 /minio/{path} 格式的路径
    # 不匹配双引号、空格、括号后的内容，确保只替换完整路径
    pattern = r'/minio/([^"\s)]+)'

    def replace_func(match):
        path = match.group(1)  # 提取 kb123/abc.jpg 部分
        return f"{minio_url}/{path}"

    return re.sub(pattern, replace_func, content)


@manager.route('/dify/retrieval', methods=['POST'])  # noqa: F821
@apikey_required
@validate_request("knowledge_id", "query")
def retrieval(tenant_id):
    req = request.json
    question = req["query"]
    kb_id = req["knowledge_id"]
    use_kg = req.get("use_kg", False)
    retrieval_setting = req.get("retrieval_setting", {})
    similarity_threshold = float(retrieval_setting.get("score_threshold", 0.0))
    top = int(retrieval_setting.get("top_k", 1024))
    metadata_condition = req.get("metadata_condition",{})
    metas = DocumentService.get_meta_by_kbs([kb_id])
 
    doc_ids = []
    try:

        e, kb = KnowledgebaseService.get_by_id(kb_id)
        if not e:
            return build_error_result(message="Knowledgebase not found!", code=settings.RetCode.NOT_FOUND)

        embd_mdl = LLMBundle(kb.tenant_id, LLMType.EMBEDDING.value, llm_name=kb.embd_id)
        print(metadata_condition)
        print("after",convert_conditions(metadata_condition))
        doc_ids.extend(meta_filter(metas, convert_conditions(metadata_condition)))
        print("doc_ids",doc_ids)
        if not doc_ids and metadata_condition:
            doc_ids = ['-999']
        ranks = settings.retrievaler.retrieval(
            question,
            embd_mdl,
            kb.tenant_id,
            [kb_id],
            page=1,
            page_size=top,
            similarity_threshold=similarity_threshold,
            vector_similarity_weight=0.3,
            top=top,
            doc_ids=doc_ids,
            rank_feature=label_question(question, [kb])
        )

        if use_kg:
            ck = settings.kg_retrievaler.retrieval(question,
                                                   [tenant_id],
                                                   [kb_id],
                                                   embd_mdl,
                                                   LLMBundle(kb.tenant_id, LLMType.CHAT))
            if ck["content_with_weight"]:
                ranks["chunks"].insert(0, ck)

        # 获取 MinIO 外部访问地址
        minio_url = _get_minio_external_url()

        records = []
        for c in ranks["chunks"]:
            e, doc = DocumentService.get_by_id( c["doc_id"])
            c.pop("vector", None)
            meta = getattr(doc, 'meta_fields', {})
            meta["doc_id"] = c["doc_id"]

            # 替换内容中的 MinIO 相对路径为外部可访问的绝对路径
            content = c["content_with_weight"]
            content = _replace_minio_urls_to_external(content, minio_url)

            records.append({
                "content": content,
                "score": c["similarity"],
                "title": c["docnm_kwd"],
                "metadata": meta
            })

        return jsonify({"records": records})
    except Exception as e:
        if str(e).find("not_found") > 0:
            return build_error_result(
                message='No chunk found! Check the chunk status please!',
                code=settings.RetCode.NOT_FOUND
            )
        logging.exception(e)
        return build_error_result(message=str(e), code=settings.RetCode.SERVER_ERROR)


