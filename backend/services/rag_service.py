"""知识检索服务。"""
import re

from models import KnowledgeBase, KnowledgeDocument


TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+", re.IGNORECASE)


def _normalize(text):
    return (text or "").strip().lower()


def _build_search_terms(query):
    tokens = TOKEN_RE.findall(_normalize(query))
    terms = set()
    for token in tokens:
        token = token.strip()
        if len(token) >= 2:
            terms.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", token):
            for idx in range(len(token) - 1):
                terms.add(token[idx: idx + 2])
    return [term for term in terms if len(term) >= 2]


def _score_document(document, terms):
    title = _normalize(document.title)
    content = _normalize(document.content)
    score = 0
    for term in terms:
        score += title.count(term) * 4
        score += content.count(term) * 2
    return score


def _build_excerpt(content, terms, max_len=160):
    raw = (content or "").strip()
    if not raw:
        return ""

    lowered = raw.lower()
    hit_pos = -1
    hit_len = 0
    for term in terms:
        pos = lowered.find(term.lower())
        if pos >= 0:
            hit_pos = pos
            hit_len = len(term)
            break

    if hit_pos < 0:
        return raw[:max_len]

    start = max(0, hit_pos - 30)
    end = min(len(raw), hit_pos + hit_len + 90)
    snippet = raw[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(raw):
        snippet = snippet + "..."
    return snippet


def search_deployment_knowledge(deployment, query, limit=3):
    knowledge_bases = KnowledgeBase.query.filter_by(
        deployment_id=deployment.id,
        status="active",
    ).all()
    if not knowledge_bases:
        return []

    knowledge_base_ids = [kb.id for kb in knowledge_bases]
    documents = KnowledgeDocument.query.filter(
        KnowledgeDocument.knowledge_base_id.in_(knowledge_base_ids),
        KnowledgeDocument.status == "published",
    ).all()
    if not documents:
        return []

    terms = _build_search_terms(query)
    if not terms:
        return []

    scored = []
    for document in documents:
        score = _score_document(document, terms)
        if score <= 0:
            continue
        scored.append({
            "document_id": document.id,
            "knowledge_base_id": document.knowledge_base_id,
            "title": document.title,
            "source_name": document.source_name,
            "score": score,
            "excerpt": _build_excerpt(document.content, terms),
        })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]
