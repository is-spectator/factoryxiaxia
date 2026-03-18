"""Core API test suite for 虾虾工厂."""
import json
import pytest


# ---------- helpers ----------

def register(client, username="testuser", email="test@t.com", password="Test1234"):
    return client.post("/api/register", json={
        "username": username, "email": email,
        "password": password, "confirm_password": password,
    })


def login(client, login_id="testuser", password="Test1234"):
    r = client.post("/api/login", json={"login_id": login_id, "password": password})
    return json.loads(r.data)["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_admin(app_module, db, username="admin1", email="admin@t.com"):
    import bcrypt
    u = app_module.User(
        username=username, email=email,
        password_hash=bcrypt.hashpw(b"Test1234", bcrypt.gensalt()).decode(),
        role="admin",
    )
    db.session.add(u)
    db.session.commit()
    return u


def seed_worker(app_module, db):
    cat = app_module.Category(name="TestCat", icon="mdi:test", sort_order=1)
    db.session.add(cat)
    db.session.commit()
    w = app_module.Worker(name="TestWorker", category_id=cat.id, hourly_rate=10.0, status="online")
    db.session.add(w)
    db.session.commit()
    return cat, w


def seed_agent_worker(app_module, db):
    cat = app_module.Category(name="AgentCat", icon="mdi:headphones", sort_order=2)
    db.session.add(cat)
    db.session.flush()

    template = app_module.AgentTemplate(
        key="support_responder_test",
        name="Support Responder Test",
        source_repo="https://example.com/repo",
        source_path="support/support-support-responder.md",
        prompt_template="客服机器人模板",
        default_tools='["knowledge_base"]',
        risk_level="medium",
        is_active=True,
    )
    db.session.add(template)
    db.session.flush()

    worker = app_module.Worker(
        name="客服机器人测试版",
        category_id=cat.id,
        hourly_rate=299.0,
        billing_unit="月租",
        status="online",
        worker_type="agent_service",
        delivery_mode="managed_deployment",
        template_key=template.key,
    )
    db.session.add(worker)
    db.session.flush()

    plan = app_module.ServicePlan(
        worker_id=worker.id,
        slug="starter",
        name="Starter",
        description="测试套餐",
        billing_cycle="monthly",
        price=299.0,
        included_conversations=500,
        max_handoffs=50,
        channel_limit=1,
        seat_limit=1,
        default_duration_hours=720,
        is_active=True,
    )
    db.session.add(plan)
    db.session.commit()
    return cat, template, worker, plan


def create_agent_deployment(client, app_module, db, publish=False, knowledge_content=None):
    register(client)
    token = login(client)
    _, _, worker, plan = seed_agent_worker(app_module, db)

    order_res = client.post("/api/orders", headers=auth(token), json={
        "worker_id": worker.id,
        "service_plan_id": plan.id,
    })
    order_id = json.loads(order_res.data)["order"]["id"]
    client.post(f"/api/orders/{order_id}/pay", headers=auth(token))

    deployment_res = client.post(f"/api/orders/{order_id}/deployments", headers=auth(token), json={
        "deployment_name": "官网客服机器人",
        "channel_type": "web_widget",
        "config": {"brand_voice": "professional"},
    })
    deployment_id = json.loads(deployment_res.data)["deployment"]["id"]

    if publish:
        client.post(f"/api/deployments/{deployment_id}/knowledge-base", headers=auth(token), json={
            "name": "默认知识库",
            "documents": [{
                "title": "客服机器人 FAQ",
                "content": knowledge_content or "我们支持 7x24 在线答复，复杂问题会转人工客服继续处理。",
                "doc_type": "faq",
                "source_name": "faq.md",
            }],
        })
        client.post(f"/api/deployments/{deployment_id}/publish", headers=auth(token))

    return token, deployment_id, worker, plan


# ==================== Auth ====================

class TestAuth:
    def test_register_success(self, client):
        r = register(client)
        assert r.status_code == 201
        data = json.loads(r.data)
        assert "token" in data
        assert data["user"]["username"] == "testuser"

    def test_register_duplicate(self, client):
        register(client)
        r = register(client)
        assert r.status_code == 409

    def test_register_short_password(self, client):
        r = client.post("/api/register", json={
            "username": "u", "email": "u@t.com",
            "password": "short", "confirm_password": "short",
        })
        assert r.status_code == 400

    def test_login_success(self, client):
        register(client)
        r = client.post("/api/login", json={"login_id": "testuser", "password": "Test1234"})
        assert r.status_code == 200
        assert "token" in json.loads(r.data)

    def test_login_wrong_password(self, client):
        register(client)
        r = client.post("/api/login", json={"login_id": "testuser", "password": "wrong123"})
        assert r.status_code == 401

    def test_profile_no_token(self, client):
        r = client.get("/api/profile")
        assert r.status_code == 401

    def test_profile_with_token(self, client):
        register(client)
        token = login(client)
        r = client.get("/api/profile", headers=auth(token))
        assert r.status_code == 200

    def test_disabled_user_rejected(self, client, app_module, db):
        register(client)
        token = login(client)
        u = app_module.User.query.filter_by(username="testuser").first()
        u.is_active = False
        db.session.commit()
        r = client.get("/api/profile", headers=auth(token))
        assert r.status_code == 401


# ==================== Categories & Workers ====================

class TestCatalog:
    def test_categories(self, client, app_module, db):
        seed_worker(app_module, db)
        r = client.get("/api/categories")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert len(data["categories"]) >= 1

    def test_workers_list(self, client, app_module, db):
        seed_worker(app_module, db)
        r = client.get("/api/workers")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["total"] >= 1

    def test_worker_detail(self, client, app_module, db):
        _, w = seed_worker(app_module, db)
        r = client.get(f"/api/workers/{w.id}")
        assert r.status_code == 200

    def test_worker_not_found(self, client):
        r = client.get("/api/workers/9999")
        assert r.status_code == 404

    def test_workers_filter_by_category(self, client, app_module, db):
        cat, _ = seed_worker(app_module, db)
        r = client.get(f"/api/workers?category_id={cat.id}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["total"] >= 1

    def test_agent_worker_detail_includes_template_and_service_plans(self, client, app_module, db):
        _, template, worker, plan = seed_agent_worker(app_module, db)
        r = client.get(f"/api/workers/{worker.id}")
        assert r.status_code == 200
        data = json.loads(r.data)["worker"]
        assert data["worker_type"] == "agent_service"
        assert data["template_key"] == template.key
        assert data["agent_template"]["key"] == template.key
        assert len(data["service_plans"]) == 1
        assert data["service_plans"][0]["slug"] == plan.slug


# ==================== Orders ====================

class TestOrders:
    def _create_order(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        r = client.post("/api/orders", headers=auth(token),
                        json={"worker_id": w.id, "duration_hours": 24})
        return token, w, r

    def test_create_order(self, client, app_module, db):
        token, w, r = self._create_order(client, app_module, db)
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data["order"]["status"] == "pending"
        assert data["order"]["total_amount"] == 240.0

    def test_create_order_no_auth(self, client, app_module, db):
        _, w = seed_worker(app_module, db)
        r = client.post("/api/orders", json={"worker_id": w.id, "duration_hours": 24})
        assert r.status_code == 401

    def test_create_order_invalid_duration(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        r = client.post("/api/orders", headers=auth(token),
                        json={"worker_id": w.id, "duration_hours": "two"})
        assert r.status_code == 400

    def test_my_orders(self, client, app_module, db):
        token, _, _ = self._create_order(client, app_module, db)
        r = client.get("/api/orders", headers=auth(token))
        assert r.status_code == 200
        assert json.loads(r.data)["total"] >= 1

    def test_order_detail(self, client, app_module, db):
        token, _, cr = self._create_order(client, app_module, db)
        oid = json.loads(cr.data)["order"]["id"]
        r = client.get(f"/api/orders/{oid}", headers=auth(token))
        assert r.status_code == 200

    def test_cancel_order(self, client, app_module, db):
        token, _, cr = self._create_order(client, app_module, db)
        oid = json.loads(cr.data)["order"]["id"]
        r = client.post(f"/api/orders/{oid}/cancel", headers=auth(token))
        assert r.status_code == 200
        assert json.loads(r.data)["order"]["status"] == "cancelled"

    def test_cancel_already_cancelled(self, client, app_module, db):
        token, _, cr = self._create_order(client, app_module, db)
        oid = json.loads(cr.data)["order"]["id"]
        client.post(f"/api/orders/{oid}/cancel", headers=auth(token))
        r = client.post(f"/api/orders/{oid}/cancel", headers=auth(token))
        assert r.status_code == 400

    def test_create_agent_order_by_service_plan(self, client, app_module, db):
        register(client)
        token = login(client)
        _, _, worker, plan = seed_agent_worker(app_module, db)
        r = client.post("/api/orders", headers=auth(token), json={
            "worker_id": worker.id,
            "service_plan_id": plan.id,
            "remark": "官网客服部署",
        })
        assert r.status_code == 201
        data = json.loads(r.data)["order"]
        assert data["order_type"] == "agent_deployment"
        assert data["service_plan_id"] == plan.id
        assert data["total_amount"] == 299.0
        assert data["duration_hours"] == 720

    def test_create_agent_order_requires_service_plan(self, client, app_module, db):
        register(client)
        token = login(client)
        _, _, worker, _ = seed_agent_worker(app_module, db)
        r = client.post("/api/orders", headers=auth(token), json={"worker_id": worker.id})
        assert r.status_code == 400


# ==================== Payment ====================

class TestPayment:
    def _paid_order(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 10})
        oid = json.loads(cr.data)["order"]["id"]
        pr = client.post(f"/api/orders/{oid}/pay", headers=auth(token))
        return token, oid, pr

    def test_pay_order(self, client, app_module, db):
        token, oid, r = self._paid_order(client, app_module, db)
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["order"]["status"] == "paid"
        assert "payment" in data

    def test_pay_idempotent(self, client, app_module, db):
        token, oid, _ = self._paid_order(client, app_module, db)
        r = client.post(f"/api/orders/{oid}/pay", headers=auth(token))
        assert r.status_code == 200

    def test_activate_order(self, client, app_module, db):
        token, oid, _ = self._paid_order(client, app_module, db)
        r = client.post(f"/api/orders/{oid}/activate", headers=auth(token))
        assert r.status_code == 200
        assert json.loads(r.data)["order"]["status"] == "active"

    def test_complete_order(self, client, app_module, db):
        token, oid, _ = self._paid_order(client, app_module, db)
        client.post(f"/api/orders/{oid}/activate", headers=auth(token))
        r = client.post(f"/api/orders/{oid}/complete", headers=auth(token))
        assert r.status_code == 200
        assert json.loads(r.data)["order"]["status"] == "completed"

    def test_refund_order(self, client, app_module, db):
        token, oid, _ = self._paid_order(client, app_module, db)
        r = client.post(f"/api/orders/{oid}/refund", headers=auth(token))
        assert r.status_code == 200
        assert json.loads(r.data)["order"]["status"] == "refunded"

    def test_payment_records(self, client, app_module, db):
        token, oid, _ = self._paid_order(client, app_module, db)
        r = client.get(f"/api/orders/{oid}/payments", headers=auth(token))
        assert r.status_code == 200
        assert len(json.loads(r.data)["payments"]) >= 1


# ==================== Reviews ====================

class TestReviews:
    def _completed_order(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 5})
        oid = json.loads(cr.data)["order"]["id"]
        client.post(f"/api/orders/{oid}/pay", headers=auth(token))
        client.post(f"/api/orders/{oid}/activate", headers=auth(token))
        client.post(f"/api/orders/{oid}/complete", headers=auth(token))
        return token, oid, w

    def test_create_review(self, client, app_module, db):
        token, oid, _ = self._completed_order(client, app_module, db)
        r = client.post(f"/api/orders/{oid}/review", headers=auth(token),
                        json={"rating": 5, "content": "Great!"})
        assert r.status_code == 201

    def test_duplicate_review(self, client, app_module, db):
        token, oid, _ = self._completed_order(client, app_module, db)
        client.post(f"/api/orders/{oid}/review", headers=auth(token),
                    json={"rating": 5, "content": "Great!"})
        r = client.post(f"/api/orders/{oid}/review", headers=auth(token),
                        json={"rating": 4, "content": "Again"})
        assert r.status_code == 400

    def test_worker_reviews(self, client, app_module, db):
        token, oid, w = self._completed_order(client, app_module, db)
        client.post(f"/api/orders/{oid}/review", headers=auth(token),
                    json={"rating": 4, "content": "Good"})
        r = client.get(f"/api/workers/{w.id}/reviews")
        assert r.status_code == 200
        assert json.loads(r.data)["total"] >= 1


# ==================== Messages ====================

class TestMessages:
    def test_messages_no_auth(self, client):
        r = client.get("/api/messages")
        assert r.status_code == 401

    def test_messages_list(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        # create and cancel order to trigger message
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 1})
        oid = json.loads(cr.data)["order"]["id"]
        client.post(f"/api/orders/{oid}/cancel", headers=auth(token))
        r = client.get("/api/messages", headers=auth(token))
        assert r.status_code == 200
        assert json.loads(r.data)["total"] >= 1

    def test_unread_count(self, client, app_module, db):
        register(client)
        token = login(client)
        r = client.get("/api/messages/unread-count", headers=auth(token))
        assert r.status_code == 200
        assert "unread_count" in json.loads(r.data)

    def test_mark_all_read(self, client, app_module, db):
        register(client)
        token = login(client)
        r = client.post("/api/messages/read-all", headers=auth(token))
        assert r.status_code == 200


# ==================== Favorites ====================

class TestFavorites:
    def test_add_favorite(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        r = client.post(f"/api/favorites/{w.id}", headers=auth(token))
        assert r.status_code == 201

    def test_favorite_idempotent(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        client.post(f"/api/favorites/{w.id}", headers=auth(token))
        r = client.post(f"/api/favorites/{w.id}", headers=auth(token))
        assert r.status_code == 200

    def test_check_favorite(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        client.post(f"/api/favorites/{w.id}", headers=auth(token))
        r = client.get(f"/api/favorites/{w.id}/check", headers=auth(token))
        assert json.loads(r.data)["is_favorited"] is True

    def test_remove_favorite(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        client.post(f"/api/favorites/{w.id}", headers=auth(token))
        r = client.delete(f"/api/favorites/{w.id}", headers=auth(token))
        assert r.status_code == 200


# ==================== Admin ====================

class TestAdmin:
    def test_admin_stats(self, client, app_module, db):
        make_admin(app_module, db)
        token = login(client, "admin1")
        r = client.get("/api/admin/stats", headers=auth(token))
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "total_users" in data
        assert "daily_orders" in data

    def test_admin_stats_no_perm(self, client):
        register(client)
        token = login(client)
        r = client.get("/api/admin/stats", headers=auth(token))
        assert r.status_code == 403

    def test_admin_users_list(self, client, app_module, db):
        make_admin(app_module, db)
        token = login(client, "admin1")
        r = client.get("/api/admin/users", headers=auth(token))
        assert r.status_code == 200

    def test_admin_create_worker(self, client, app_module, db):
        make_admin(app_module, db)
        token = login(client, "admin1")
        cat = app_module.Category(name="AdminCat", icon="mdi:t", sort_order=1)
        db.session.add(cat)
        db.session.commit()
        r = client.post("/api/admin/workers", headers=auth(token),
                        json={"name": "NewBot", "category_id": cat.id, "hourly_rate": 5.0})
        assert r.status_code == 201

    def test_admin_delete_worker_soft(self, client, app_module, db):
        make_admin(app_module, db)
        token = login(client, "admin1")
        register(client, "u2", "u2@t.com")
        t2 = login(client, "u2")
        _, w = seed_worker(app_module, db)
        client.post("/api/orders", headers=auth(t2),
                    json={"worker_id": w.id, "duration_hours": 1})
        r = client.delete(f"/api/admin/workers/{w.id}", headers=auth(token))
        assert r.status_code == 200
        assert "下架" in json.loads(r.data)["message"]

    def test_admin_list_service_plans(self, client, app_module, db):
        make_admin(app_module, db)
        token = login(client, "admin1")
        _, _, _, plan = seed_agent_worker(app_module, db)
        r = client.get("/api/admin/service-plans", headers=auth(token))
        assert r.status_code == 200
        data = json.loads(r.data)
        assert any(p["id"] == plan.id for p in data["service_plans"])

    def test_admin_list_audit_logs(self, client, app_module, db):
        make_admin(app_module, db)
        owner_token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="我们支持 7x24 在线客服。",
        )
        client.post(f"/api/chat/{deployment_id}/message", json={
            "message": "你们支持在线客服吗？",
        })

        token = login(client, "admin1")
        r = client.get("/api/admin/audit-logs", headers=auth(token))
        assert r.status_code == 200
        data = json.loads(r.data)
        assert any(log["deployment_id"] == deployment_id for log in data["audit_logs"])


class TestDeployments:
    def test_create_deployment_from_paid_order(self, client, app_module, db):
        register(client)
        token = login(client)
        _, _, worker, plan = seed_agent_worker(app_module, db)
        order_res = client.post("/api/orders", headers=auth(token), json={
            "worker_id": worker.id,
            "service_plan_id": plan.id,
        })
        order_id = json.loads(order_res.data)["order"]["id"]
        client.post(f"/api/orders/{order_id}/pay", headers=auth(token))

        r = client.post(f"/api/orders/{order_id}/deployments", headers=auth(token), json={
            "deployment_name": "官网客服机器人",
            "channel_type": "web_widget",
            "config": {"brand_voice": "professional"},
        })
        assert r.status_code == 201
        data = json.loads(r.data)["deployment"]
        assert data["deployment_name"] == "官网客服机器人"
        assert data["template_key"] == "support_responder_test"
        assert data["status"] == "pending_setup"
        assert data["organization_name"] == "testuser 的团队"
        assert data["public_token"]

    def test_list_deployments_requires_auth(self, client):
        r = client.get("/api/deployments")
        assert r.status_code == 401

    def test_upload_knowledge_base_and_publish(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(client, app_module, db)
        kb_res = client.post(f"/api/deployments/{deployment_id}/knowledge-base", headers=auth(token), json={
            "name": "售前 FAQ",
            "documents": [{
                "title": "服务时间",
                "content": "我们支持 7x24 在线答复，并在复杂场景下转人工。",
                "doc_type": "faq",
                "source_name": "service-time.md",
            }],
        })
        assert kb_res.status_code == 201
        kb_data = json.loads(kb_res.data)
        assert kb_data["knowledge_base"]["name"] == "售前 FAQ"
        assert len(kb_data["documents"]) == 1

        publish_res = client.post(f"/api/deployments/{deployment_id}/publish", headers=auth(token))
        assert publish_res.status_code == 200
        publish_data = json.loads(publish_res.data)
        assert publish_data["deployment"]["status"] == "active"
        assert publish_data["knowledge_bases"][0]["status"] == "active"

    def test_update_deployment_config_and_list_audit_logs(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(client, app_module, db, publish=True)
        update_res = client.put(f"/api/deployments/{deployment_id}/config", headers=auth(token), json={
            "brand_voice": "warm",
            "forbidden_topics": ["退款"],
            "sensitive_keywords": ["赔偿"],
            "pii_masking_enabled": True,
        })
        assert update_res.status_code == 200
        deployment = json.loads(update_res.data)["deployment"]
        assert deployment["config"]["brand_voice"] == "warm"
        assert deployment["config"]["forbidden_topics"] == ["退款"]

        audit_res = client.get(f"/api/deployments/{deployment_id}/audit-logs", headers=auth(token))
        assert audit_res.status_code == 200
        audit_logs = json.loads(audit_res.data)["audit_logs"]
        assert any(log["action_type"] == "deployment.config_updated" for log in audit_logs)


class TestChat:
    def test_chat_message_returns_answer_and_metrics(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="我们支持 7x24 在线客服，低置信度问题会自动转人工继续处理。",
        )

        chat_res = client.post(f"/api/chat/{deployment_id}/message", json={
            "message": "你们支持7x24在线吗？",
            "visitor_name": "访客 A",
        })
        assert chat_res.status_code == 200
        chat_data = json.loads(chat_res.data)
        assert "7x24" in chat_data["assistant_message"]["content"]
        assert chat_data["session"]["message_count"] == 2

        sessions_res = client.get(f"/api/chat/{deployment_id}/sessions", headers=auth(token))
        assert sessions_res.status_code == 200
        sessions_data = json.loads(sessions_res.data)
        assert sessions_data["total"] == 1

        metrics_res = client.get(f"/api/chat/{deployment_id}/metrics", headers=auth(token))
        assert metrics_res.status_code == 200
        metrics = json.loads(metrics_res.data)["metrics"]
        assert metrics["messages_in"] == 1
        assert metrics["messages_out"] == 1
        assert metrics["knowledge_hits"] >= 1

    def test_public_chat_by_token_masks_pii_and_records_audit(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="请客户留下邮箱后，我们会安排人工联系。",
        )
        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        public_token = json.loads(detail_res.data)["deployment"]["public_token"]

        chat_res = client.post(f"/api/public/chat/{public_token}/message", json={
            "message": "我的邮箱是 test@example.com，电话是13812345678",
            "visitor_name": "访客 D",
        })
        assert chat_res.status_code == 200
        session_id = json.loads(chat_res.data)["session"]["id"]

        sessions_res = client.get(
            f"/api/chat/{deployment_id}/sessions?include_messages=1",
            headers=auth(token),
        )
        messages = json.loads(sessions_res.data)["sessions"][0]["messages"]
        user_message = next(message for message in messages if message["role"] == "user")
        assert "[masked-email]" in user_message["content"]
        assert "[masked-phone]" in user_message["content"]

        audit_res = client.get(f"/api/deployments/{deployment_id}/audit-logs", headers=auth(token))
        audit_logs = json.loads(audit_res.data)["audit_logs"]
        assert any(
            log["action_type"] == "chat.turn" and log["details"]["access_mode"] == "public_token"
            for log in audit_logs
        )
        assert session_id == json.loads(chat_res.data)["session"]["id"]

    def test_chat_low_confidence_creates_handoff(self, client, app_module, db):
        _, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="这里只记录营业时间和基础联系方式。",
        )

        chat_res = client.post(f"/api/chat/{deployment_id}/message", json={
            "message": "我要投诉并申请退款",
            "visitor_name": "访客 B",
        })
        assert chat_res.status_code == 200
        chat_data = json.loads(chat_res.data)
        assert chat_data["session"]["needs_handoff"] is True
        assert chat_data["handoff_ticket"] is not None
        assert chat_data["handoff_ticket"]["status"] == "open"

    def test_manual_handoff_endpoint(self, client, app_module, db):
        _, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="我们支持 7x24 在线客服。",
        )

        chat_res = client.post(f"/api/chat/{deployment_id}/message", json={
            "message": "你们能提供在线支持吗？",
            "visitor_name": "访客 C",
        })
        session_id = json.loads(chat_res.data)["session"]["id"]

        handoff_res = client.post(f"/api/chat/{deployment_id}/handoff", json={
            "session_id": session_id,
            "reason": "需要人工报价",
            "summary": "访客希望进一步联系销售",
        })
        assert handoff_res.status_code == 201
        handoff_data = json.loads(handoff_res.data)
        assert handoff_data["handoff_ticket"]["reason"] == "需要人工报价"

    def test_forbidden_topic_triggers_guardrails(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="这里是基础 FAQ。",
        )
        client.put(f"/api/deployments/{deployment_id}/config", headers=auth(token), json={
            "forbidden_topics": ["退款"],
            "brand_voice": "concise",
        })
        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        public_token = json.loads(detail_res.data)["deployment"]["public_token"]

        chat_res = client.post(f"/api/public/chat/{public_token}/message", json={
            "message": "我要退款",
        })
        assert chat_res.status_code == 200
        chat_data = json.loads(chat_res.data)
        assert "超出了当前机器人可直接处理的范围" in chat_data["assistant_message"]["content"]
        assert chat_data["session"]["needs_handoff"] is True
        assert chat_data["handoff_ticket"] is not None


# ==================== Security / Infra ====================

class TestSecurity:
    def test_security_headers(self, client):
        r = client.get("/api/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert "1; mode=block" in r.headers.get("X-XSS-Protection", "")

    def test_health_check(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["status"] == "ok"
        assert "database" in data

    def test_api_docs(self, client):
        r = client.get("/api/docs")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "openapi" in data
        assert "paths" in data

    def test_rate_limiter_loaded(self, app_module):
        assert hasattr(app_module, "limiter")

    def test_json_formatter(self, app_module):
        import logging
        fmt = app_module.JsonFormatter()
        rec = logging.LogRecord("t", logging.INFO, "", 0, "msg", (), None)
        out = json.loads(fmt.format(rec))
        assert "timestamp" in out
        assert out["message"] == "msg"

    def test_recommendations(self, client, app_module, db):
        seed_worker(app_module, db)
        r = client.get("/api/recommendations")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["strategy"] == "popular"


class TestSchemaMigrations:
    def test_ensure_order_schema_adds_missing_activated_at(self, app_module, db):
        with app_module.app.app_context():
            db.drop_all()
            db.session.execute(app_module.text("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_no VARCHAR(30) NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL,
                    worker_id INTEGER NOT NULL,
                    duration_hours INTEGER NOT NULL,
                    total_amount NUMERIC(10, 2) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    remark TEXT DEFAULT '',
                    paid_at DATETIME DEFAULT NULL,
                    completed_at DATETIME DEFAULT NULL,
                    cancelled_at DATETIME DEFAULT NULL,
                    refunded_at DATETIME DEFAULT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.commit()

            app_module.ensure_order_schema()

            column_names = {column["name"] for column in app_module.inspect(db.engine).get_columns("orders")}
            assert "activated_at" in column_names

    def test_ensure_order_schema_is_idempotent(self, app_module, db):
        with app_module.app.app_context():
            db.create_all()
            app_module.ensure_order_schema()
            column_names = [column["name"] for column in app_module.inspect(db.engine).get_columns("orders") if column["name"] == "activated_at"]
            assert column_names == ["activated_at"]
