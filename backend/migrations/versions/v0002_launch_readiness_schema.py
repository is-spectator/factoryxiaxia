"""0002: 对齐上线阶段所需字段和索引。"""

from migration_manager import ensure_column, ensure_index


VERSION = "0002"
NAME = "launch_readiness_schema"


def upgrade(connection, _app_module):
    column_specs = [
        ("orders", "activated_at", "DATETIME NULL"),
        ("orders", "order_type", "VARCHAR(30) DEFAULT 'rental'"),
        ("orders", "service_plan_id", "INTEGER NULL"),
        ("workers", "worker_type", "VARCHAR(30) DEFAULT 'general'"),
        ("workers", "delivery_mode", "VARCHAR(30) DEFAULT 'manual_service'"),
        ("workers", "launch_stage", "VARCHAR(20) DEFAULT 'public'"),
        ("workers", "template_key", "VARCHAR(80) NULL"),
        ("deployments", "public_token", "VARCHAR(120) NULL"),
        ("deployments", "knowledge_version", "VARCHAR(40) NULL"),
        ("deployments", "knowledge_last_published_at", "DATETIME NULL"),
        ("deployments", "knowledge_summary_json", "TEXT NULL"),
    ]
    for table_name, column_name, column_sql in column_specs:
        ensure_column(connection, table_name, column_name, column_sql)

    index_specs = [
        ("orders", "idx_orders_user_id", ["user_id"], False),
        ("orders", "idx_orders_worker_id", ["worker_id"], False),
        ("orders", "idx_orders_status", ["status"], False),
        ("orders", "idx_orders_created_at", ["created_at"], False),
        ("orders", "idx_orders_service_plan_id", ["service_plan_id"], False),
        ("payments", "idx_payments_order_id", ["order_id"], False),
        ("payments", "idx_payments_user_id", ["user_id"], False),
        ("reviews", "idx_reviews_worker_id", ["worker_id"], False),
        ("reviews", "idx_reviews_user_id", ["user_id"], False),
        ("messages", "idx_messages_user_id", ["user_id"], False),
        ("messages", "idx_messages_is_read", ["is_read"], False),
        ("messages", "idx_messages_created_at", ["created_at"], False),
        ("favorites", "idx_favorites_user_id", ["user_id"], False),
        ("workers", "idx_workers_category_id", ["category_id"], False),
        ("workers", "idx_workers_status", ["status"], False),
        ("workers", "idx_workers_worker_type", ["worker_type"], False),
        ("service_plans", "idx_service_plans_worker_id", ["worker_id"], False),
        ("deployments", "idx_deployments_user_id", ["user_id"], False),
        ("deployments", "idx_deployments_status", ["status"], False),
        ("deployments", "uq_deployments_public_token", ["public_token"], True),
        ("deployments", "idx_deployments_public_token", ["public_token"], False),
        ("knowledge_bases", "idx_knowledge_bases_deployment_id", ["deployment_id"], False),
        ("knowledge_documents", "idx_knowledge_documents_knowledge_base_id", ["knowledge_base_id"], False),
        ("knowledge_documents", "idx_knowledge_documents_status", ["status"], False),
        ("conversation_sessions", "idx_conversation_sessions_deployment_id", ["deployment_id"], False),
        ("conversation_sessions", "idx_conversation_sessions_status", ["status"], False),
        ("conversation_messages", "idx_conversation_messages_session_id", ["session_id"], False),
        ("handoff_tickets", "idx_handoff_tickets_deployment_id", ["deployment_id"], False),
        ("handoff_tickets", "idx_handoff_tickets_status", ["status"], False),
        ("usage_records", "idx_usage_records_deployment_id", ["deployment_id"], False),
        ("usage_records", "idx_usage_records_metric_type", ["metric_type"], False),
        ("audit_logs", "idx_audit_logs_deployment_id", ["deployment_id"], False),
        ("audit_logs", "idx_audit_logs_action_type", ["action_type"], False),
    ]
    for table_name, index_name, columns, unique in index_specs:
        ensure_index(connection, table_name, index_name, columns, unique=unique)
