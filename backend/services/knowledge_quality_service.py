"""知识库质量闸门与发布摘要服务。"""

import hashlib

from models import KnowledgeBase, KnowledgeDocument


MIN_PUBLISH_DOCUMENTS = 1
MIN_DOCUMENT_CHARS = 8
MAX_DOCUMENT_CHARS = 20000


def _normalize_title(title):
    return " ".join(str(title or "").split()).strip().lower()


def _effective_char_count(content):
    return len("".join(str(content or "").split()))


def validate_document_content(title, content):
    normalized_title = " ".join(str(title or "").split()).strip()
    normalized_content = str(content or "").strip()
    effective_char_count = _effective_char_count(normalized_content)

    if not normalized_title:
        return None, "知识文档标题不能为空"
    if not normalized_content:
        return None, f"知识文档《{normalized_title}》内容不能为空"
    if effective_char_count < MIN_DOCUMENT_CHARS:
        return None, f"知识文档《{normalized_title}》内容过短，请至少补充 {MIN_DOCUMENT_CHARS} 个非空白字符"
    if len(normalized_content) > MAX_DOCUMENT_CHARS:
        return None, f"知识文档《{normalized_title}》内容过长，请控制在 {MAX_DOCUMENT_CHARS} 个字符以内"

    return {
        "title": normalized_title,
        "content": normalized_content,
        "char_count": effective_char_count,
    }, None


def validate_upload_documents(knowledge_base, documents_payload):
    existing_titles = set()
    if knowledge_base:
        existing_documents = KnowledgeDocument.query.filter_by(
            knowledge_base_id=knowledge_base.id
        ).all()
        existing_titles = {
            _normalize_title(document.title)
            for document in existing_documents
            if _normalize_title(document.title)
        }

    normalized_documents = []
    new_titles = set()
    for item in documents_payload:
        title = (item.get("title") or "").strip()
        content = item.get("content") or ""
        normalized, error = validate_document_content(title, content)
        if error:
            return None, error

        title_key = _normalize_title(normalized["title"])
        if title_key in new_titles:
            return None, f"本次上传中存在重复文档标题：{normalized['title']}"
        if title_key in existing_titles:
            return None, f"知识库中已存在同名文档：{normalized['title']}"

        new_titles.add(title_key)
        normalized_documents.append({
            "title": normalized["title"],
            "content": normalized["content"],
            "char_count": normalized["char_count"],
            "doc_type": (item.get("doc_type") or "faq").strip() or "faq",
            "source_name": (item.get("source_name") or "").strip(),
        })

    return normalized_documents, None


def collect_publishable_knowledge_bases(deployment_id):
    knowledge_bases = KnowledgeBase.query.filter_by(
        deployment_id=deployment_id
    ).order_by(KnowledgeBase.id.asc()).all()

    if not knowledge_bases:
        raise ValueError("请先上传知识库")

    publishable_bases = []
    total_documents = 0
    for knowledge_base in knowledge_bases:
        documents = KnowledgeDocument.query.filter_by(
            knowledge_base_id=knowledge_base.id
        ).order_by(KnowledgeDocument.id.asc()).all()
        if not documents:
            continue

        local_titles = set()
        for document in documents:
            normalized, error = validate_document_content(document.title, document.content)
            if error:
                raise ValueError(error)
            title_key = _normalize_title(document.title)
            if title_key in local_titles:
                raise ValueError(f"知识库《{knowledge_base.name}》存在重复文档标题：{document.title}")
            local_titles.add(title_key)
            document.char_count = normalized["char_count"]
        total_documents += len(documents)
        publishable_bases.append(knowledge_base)

    if total_documents < MIN_PUBLISH_DOCUMENTS:
        raise ValueError(f"请至少准备 {MIN_PUBLISH_DOCUMENTS} 篇知识文档后再发布")
    if not publishable_bases:
        raise ValueError("请至少上传一篇有效知识文档")

    return publishable_bases


def build_knowledge_summary(knowledge_bases):
    base_summaries = []
    version_parts = []
    total_documents = 0
    total_chars = 0
    last_published_at = None

    for knowledge_base in knowledge_bases:
        documents = KnowledgeDocument.query.filter_by(
            knowledge_base_id=knowledge_base.id,
            status="published",
        ).order_by(KnowledgeDocument.id.asc()).all()
        if not documents:
            continue

        sample_titles = [document.title for document in documents[:3]]
        base_char_count = sum(document.char_count or _effective_char_count(document.content) for document in documents)
        total_documents += len(documents)
        total_chars += base_char_count
        if knowledge_base.published_at and (last_published_at is None or knowledge_base.published_at > last_published_at):
            last_published_at = knowledge_base.published_at

        base_summaries.append({
            "id": knowledge_base.id,
            "name": knowledge_base.name,
            "description": knowledge_base.description,
            "document_count": len(documents),
            "total_char_count": base_char_count,
            "sample_titles": sample_titles,
            "published_at": knowledge_base.published_at.isoformat() if knowledge_base.published_at else None,
        })

        for document in documents:
            version_parts.append(
                f"{knowledge_base.id}:{document.id}:{document.title}:{document.char_count or 0}:{document.status}"
            )

    version_hash = hashlib.sha1("|".join(version_parts).encode("utf-8")).hexdigest()[:12] if version_parts else ""
    return {
        "knowledge_base_count": len(base_summaries),
        "published_document_count": total_documents,
        "total_char_count": total_chars,
        "bases": base_summaries,
        "last_published_at": last_published_at.isoformat() if last_published_at else None,
    }, (f"kb-{version_hash}" if version_hash else "")
