"""0001: 基于当前 SQLAlchemy 模型创建基线表结构。"""

VERSION = "0001"
NAME = "model_baseline"


def upgrade(connection, app_module):
    app_module.db.metadata.create_all(bind=connection)
