"""部署相关服务。"""
import datetime

from models import Deployment, KnowledgeBase, KnowledgeDocument


def user_can_manage_deployment(user, deployment):
    if not user or not deployment:
        return False
    if deployment.user_id == user.id:
        return True
    return (user.role or "user") in ("admin", "operator")


def get_manageable_deployment(user, deployment_id):
    deployment = Deployment.query.get(deployment_id)
    if not deployment:
        return None
    if not user_can_manage_deployment(user, deployment):
        return None
    return deployment


def get_primary_knowledge_base(deployment_id):
    return KnowledgeBase.query.filter_by(deployment_id=deployment_id).order_by(KnowledgeBase.id.asc()).first()


def publish_deployment(deployment):
    knowledge_bases = KnowledgeBase.query.filter_by(deployment_id=deployment.id).all()
    if not knowledge_bases:
        raise ValueError("请先上传知识库")

    total_documents = 0
    now = datetime.datetime.utcnow()
    for knowledge_base in knowledge_bases:
        documents = KnowledgeDocument.query.filter_by(knowledge_base_id=knowledge_base.id).all()
        if not documents:
            continue

        total_documents += len(documents)
        knowledge_base.status = "active"
        knowledge_base.published_at = now
        for document in documents:
            document.status = "published"

    if total_documents == 0:
        raise ValueError("请至少上传一篇知识文档")

    if deployment.status in ("pending_setup", "pending_review"):
        deployment.status = "active"
    if not deployment.started_at:
        deployment.started_at = now

    return knowledge_bases
