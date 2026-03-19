"""数据库迁移与维护命令入口。"""

import argparse
import os
import sys


os.environ.setdefault("SKIP_MIGRATION_CHECK", "1")
os.environ.setdefault("SKIP_RUNTIME_BOOTSTRAP", "1")

import app as app_module  # noqa: E402
from migration_manager import apply_migrations, describe_migration_state  # noqa: E402


def print_state(state):
    print("已应用迁移:")
    if state["applied"]:
        for item in state["applied"]:
            print(f"  - {item['version']} {item['name']}")
    else:
        print("  (无)")

    print("待执行迁移:")
    if state["pending"]:
        for item in state["pending"]:
            print(f"  - {item['version']} {item['name']}")
    else:
        print("  (无)")


def run_migrate():
    with app_module.app.app_context():
        applied = apply_migrations(app_module)
        if applied:
            for item in applied:
                print(f"已执行迁移 {item['version']} {item['name']}")
        else:
            print("没有待执行的迁移")


def run_bootstrap():
    with app_module.app.app_context():
        app_module.ensure_initial_admin_account()
        app_module.bootstrap_agent_foundation()
        app_module.db.session.commit()
        print("已完成运行时初始化")


def run_status():
    with app_module.app.app_context():
        print_state(describe_migration_state(app_module))


def main():
    parser = argparse.ArgumentParser(description="虾虾工厂数据库迁移工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("migrate", help="执行所有待执行迁移")
    subparsers.add_parser("bootstrap", help="执行运行时初始化（管理员/官方员工）")
    subparsers.add_parser("status", help="查看迁移状态")

    args = parser.parse_args()
    if args.command == "migrate":
        run_migrate()
        return 0
    if args.command == "bootstrap":
        run_bootstrap()
        return 0
    if args.command == "status":
        run_status()
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
