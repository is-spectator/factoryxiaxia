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


def seed_kongkong_worker(app_module, db):
    cat = app_module.Category(name="RuntimeCat", icon="mdi:cube-outline", sort_order=1)
    db.session.add(cat)
    db.session.flush()

    template = app_module.AgentTemplate(
        key="kongkong_openclaw_workspace_test",
        name="空空 OpenClaw Workspace Test",
        source_repo="https://github.com/openclaw/openclaw",
        source_path="install/docker",
        prompt_template="空空工作台模板",
        default_tools='["openclaw_workspace"]',
        risk_level="high",
        is_active=True,
    )
    db.session.add(template)
    db.session.flush()

    worker = app_module.Worker(
        name="空空测试版",
        category_id=cat.id,
        hourly_rate=2.0,
        billing_unit="￥99/月｜￥2/小时",
        status="online",
        worker_type="agent_service",
        delivery_mode="managed_deployment",
        template_key=template.key,
        runtime_kind="openclaw_managed",
    )
    db.session.add(worker)
    db.session.flush()

    monthly_plan = app_module.ServicePlan(
        worker_id=worker.id,
        slug="monthly",
        name="Monthly",
        description="包月空空实例",
        billing_cycle="monthly",
        price=99.0,
        included_conversations=0,
        max_handoffs=0,
        channel_limit=1,
        seat_limit=1,
        default_duration_hours=720,
        instance_type="openclaw-standard",
        cpu_limit=1.0,
        memory_limit_mb=2048,
        storage_limit_gb=10,
        is_active=True,
    )
    hourly_plan = app_module.ServicePlan(
        worker_id=worker.id,
        slug="hourly",
        name="Hourly",
        description="按小时购买空空实例",
        billing_cycle="hourly",
        price=2.0,
        included_conversations=0,
        max_handoffs=0,
        channel_limit=1,
        seat_limit=1,
        default_duration_hours=1,
        instance_type="openclaw-hourly",
        cpu_limit=1.0,
        memory_limit_mb=2048,
        storage_limit_gb=10,
        is_active=True,
    )
    db.session.add(monthly_plan)
    db.session.add(hourly_plan)
    db.session.commit()
    return cat, template, worker, monthly_plan, hourly_plan


def create_agent_deployment(client, app_module, db, publish=False, knowledge_content=None, config=None, channel_type="web_widget"):
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
        "channel_type": channel_type,
        "config": {"brand_voice": "professional", **(config or {})},
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


def bootstrap_official_agents(app_module, db):
    with app_module.app.app_context():
        app_module.bootstrap_agent_foundation()
        db.session.commit()


def buy_publish_and_get_token(client, token, worker_id, service_plan_id, knowledge_content, channel_type="web_widget"):
    order_res = client.post("/api/orders", headers=auth(token), json={
        "worker_id": worker_id,
        "service_plan_id": service_plan_id,
    })
    order_id = json.loads(order_res.data)["order"]["id"]
    client.post(f"/api/orders/{order_id}/pay", headers=auth(token))

    deploy_res = client.post(f"/api/orders/{order_id}/deployments", headers=auth(token), json={
        "deployment_name": "官方数字员工实例",
        "channel_type": channel_type,
    })
    deployment_id = json.loads(deploy_res.data)["deployment"]["id"]

    client.post(f"/api/deployments/{deployment_id}/knowledge-base", headers=auth(token), json={
        "name": "官方知识库",
        "documents": [{
            "title": "官方知识文档",
            "content": knowledge_content,
            "doc_type": "faq",
            "source_name": "official.md",
        }],
    })
    client.post(f"/api/deployments/{deployment_id}/publish", headers=auth(token))

    detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
    public_token = json.loads(detail_res.data)["deployment"]["public_token"]
    return deployment_id, public_token


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

    def test_kongkong_worker_detail_includes_runtime_kind_and_plans(self, client, app_module, db):
        _, template, worker, monthly_plan, hourly_plan = seed_kongkong_worker(app_module, db)
        r = client.get(f"/api/workers/{worker.id}")
        assert r.status_code == 200
        data = json.loads(r.data)["worker"]
        assert data["runtime_kind"] == "openclaw_managed"
        assert data["template_key"] == template.key
        assert {plan["slug"] for plan in data["service_plans"]} == {"monthly", "hourly"}
        monthly = next(plan for plan in data["service_plans"] if plan["slug"] == "monthly")
        hourly = next(plan for plan in data["service_plans"] if plan["slug"] == "hourly")
        assert monthly["price"] == 99.0
        assert hourly["price"] == 2.0


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

    def test_create_kongkong_hourly_order_uses_duration_multiplier(self, client, app_module, db):
        register(client)
        token = login(client)
        _, _, worker, _, hourly_plan = seed_kongkong_worker(app_module, db)
        r = client.post("/api/orders", headers=auth(token), json={
            "worker_id": worker.id,
            "service_plan_id": hourly_plan.id,
            "duration_hours": 6,
        })
        assert r.status_code == 201
        data = json.loads(r.data)["order"]
        assert data["order_type"] == "agent_deployment"
        assert data["service_plan_billing_cycle"] == "hourly"
        assert data["duration_hours"] == 6
        assert data["total_amount"] == 12.0


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

    def test_submit_payment_review_for_manual_confirmation(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 10})
        oid = json.loads(cr.data)["order"]["id"]

        r = client.post(f"/api/orders/{oid}/payment-review", headers=auth(token), json={
            "method": "bank_transfer",
            "payer_name": "测试采购",
            "external_ref": "BANK-20260319-001",
            "note": "已完成公司转账，请审核",
        })
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["order"]["status"] == "payment_pending"
        assert data["payment"]["status"] == "pending_review"

    def test_mock_pay_disabled_in_production(self, client, app_module, db, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 10})
        oid = json.loads(cr.data)["order"]["id"]

        r = client.post(f"/api/orders/{oid}/pay", headers=auth(token), json={"method": "mock"})
        assert r.status_code == 400
        assert "已关闭模拟支付" in json.loads(r.data)["error"]


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

    def test_admin_confirm_and_reject_payment_review(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 10})
        oid = json.loads(cr.data)["order"]["id"]
        client.post(f"/api/orders/{oid}/payment-review", headers=auth(token), json={
            "method": "bank_transfer",
            "note": "请审核收款",
        })

        make_admin(app_module, db)
        admin_token = login(client, "admin1")

        confirm_res = client.post(f"/api/admin/orders/{oid}/confirm-payment", headers=auth(admin_token))
        assert confirm_res.status_code == 200
        assert json.loads(confirm_res.data)["order"]["status"] == "paid"

        cr2 = client.post("/api/orders", headers=auth(token),
                          json={"worker_id": w.id, "duration_hours": 12})
        oid2 = json.loads(cr2.data)["order"]["id"]
        client.post(f"/api/orders/{oid2}/payment-review", headers=auth(token), json={
            "method": "bank_transfer",
            "note": "第二笔待审核",
        })

        reject_res = client.post(f"/api/admin/orders/{oid2}/reject-payment", headers=auth(admin_token))
        assert reject_res.status_code == 200
        assert json.loads(reject_res.data)["order"]["status"] == "pending"


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
        assert data["public_token"] is None

    def test_create_kongkong_deployment_auto_provisions_instance(self, client, app_module, db):
        register(client)
        token = login(client)
        _, _, worker, monthly_plan, _ = seed_kongkong_worker(app_module, db)
        order_res = client.post("/api/orders", headers=auth(token), json={
            "worker_id": worker.id,
            "service_plan_id": monthly_plan.id,
        })
        order_id = json.loads(order_res.data)["order"]["id"]
        client.post(f"/api/orders/{order_id}/pay", headers=auth(token))

        r = client.post(f"/api/orders/{order_id}/deployments", headers=auth(token), json={
            "deployment_name": "空空工作台",
            "channel_type": "workspace",
        })
        assert r.status_code == 201
        deployment = json.loads(r.data)["deployment"]
        assert deployment["runtime_kind"] == "openclaw_managed"
        assert deployment["status"] == "active"
        assert deployment["kongkong_instance"] is not None
        assert deployment["kongkong_instance"]["status"] == "running"
        assert deployment["kongkong_instance"]["entry_url"].endswith("/kongkong/mock/kongkong-1/")

    def test_kongkong_deployment_blocks_knowledge_publish_endpoints(self, client, app_module, db):
        register(client)
        token = login(client)
        _, _, worker, monthly_plan, _ = seed_kongkong_worker(app_module, db)
        order_res = client.post("/api/orders", headers=auth(token), json={
            "worker_id": worker.id,
            "service_plan_id": monthly_plan.id,
        })
        order_id = json.loads(order_res.data)["order"]["id"]
        client.post(f"/api/orders/{order_id}/pay", headers=auth(token))

        deploy_res = client.post(f"/api/orders/{order_id}/deployments", headers=auth(token), json={
            "deployment_name": "空空工作台",
            "channel_type": "workspace",
        })
        deployment_id = json.loads(deploy_res.data)["deployment"]["id"]

        kb_res = client.post(f"/api/deployments/{deployment_id}/knowledge-base", headers=auth(token), json={
            "title": "不适用",
            "content": "不适用",
        })
        assert kb_res.status_code == 400
        assert "不使用知识库发布流程" in json.loads(kb_res.data)["error"]

        publish_res = client.post(f"/api/deployments/{deployment_id}/publish", headers=auth(token))
        assert publish_res.status_code == 400
        assert "无需单独发布" in json.loads(publish_res.data)["error"]

    def test_kongkong_instance_launch_link_and_controls(self, client, app_module, db):
        register(client)
        token = login(client)
        _, _, worker, monthly_plan, _ = seed_kongkong_worker(app_module, db)
        order_res = client.post("/api/orders", headers=auth(token), json={
            "worker_id": worker.id,
            "service_plan_id": monthly_plan.id,
        })
        order_id = json.loads(order_res.data)["order"]["id"]
        client.post(f"/api/orders/{order_id}/pay", headers=auth(token))

        deploy_res = client.post(f"/api/orders/{order_id}/deployments", headers=auth(token), json={
            "deployment_name": "空空工作台",
            "channel_type": "workspace",
        })
        deployment = json.loads(deploy_res.data)["deployment"]
        instance_id = deployment["kongkong_instance"]["id"]

        list_res = client.get("/api/kongkong/instances", headers=auth(token))
        assert list_res.status_code == 200
        assert len(json.loads(list_res.data)["instances"]) == 1

        launch_res = client.post(f"/api/kongkong/instances/{instance_id}/launch-link", headers=auth(token))
        assert launch_res.status_code == 200
        launch_payload = json.loads(launch_res.data)["launch"]
        assert launch_payload["mode"] == "mock"
        assert launch_payload["launch_url"].endswith("/kongkong/mock/kongkong-1/")
        assert launch_payload["gateway_token"]

        suspend_res = client.post(f"/api/kongkong/instances/{instance_id}/suspend", headers=auth(token))
        assert suspend_res.status_code == 200
        assert json.loads(suspend_res.data)["instance"]["status"] == "suspended"

        start_res = client.post(f"/api/kongkong/instances/{instance_id}/start", headers=auth(token))
        assert start_res.status_code == 200
        assert json.loads(start_res.data)["instance"]["status"] == "running"

    def test_kongkong_launch_link_rejects_mock_mode_outside_test(self, client, app_module, db, monkeypatch):
        register(client, "kongmock", "kongmock@t.com")
        token = login(client, "kongmock")
        _, _, worker, monthly_plan, _ = seed_kongkong_worker(app_module, db)
        order_res = client.post("/api/orders", headers=auth(token), json={
            "worker_id": worker.id,
            "service_plan_id": monthly_plan.id,
        })
        order_id = json.loads(order_res.data)["order"]["id"]
        client.post(f"/api/orders/{order_id}/pay", headers=auth(token))

        deploy_res = client.post(f"/api/orders/{order_id}/deployments", headers=auth(token), json={
            "deployment_name": "空空 mock 工作台",
            "channel_type": "workspace",
        })
        deployment = json.loads(deploy_res.data)["deployment"]
        instance_id = deployment["kongkong_instance"]["id"]

        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("KONGKONG_RUNTIME_MODE", "mock")

        launch_res = client.post(f"/api/kongkong/instances/{instance_id}/launch-link", headers=auth(token))
        assert launch_res.status_code == 409
        assert "mock 模式" in json.loads(launch_res.data)["error"]

    def test_pending_deployment_does_not_expose_public_token_or_public_api(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(client, app_module, db)
        deployment = db.session.get(app_module.Deployment, deployment_id)
        deployment.public_token = "legacy-pending-token"
        db.session.commit()

        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        assert detail_res.status_code == 200
        assert json.loads(detail_res.data)["deployment"]["public_token"] is None

        public_res = client.post("/api/public/chat/legacy-pending-token/message", json={
            "message": "现在可以用了吗？",
            "visitor_name": "验收用户",
        })
        assert public_res.status_code == 404
        assert json.loads(public_res.data)["error"] == "公开聊天入口不存在"

    def test_list_deployments_requires_auth(self, client):
        r = client.get("/api/deployments")
        assert r.status_code == 401
        assert "请先登录".encode("utf-8") in r.data
        assert b"\\u8bf7\\u5148\\u767b\\u5f55" not in r.data

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
        assert publish_data["deployment"]["knowledge_version"].startswith("kb-")
        assert publish_data["deployment"]["knowledge_summary"]["published_document_count"] == 1

    def test_reject_short_or_duplicate_knowledge_documents(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(client, app_module, db)

        short_res = client.post(f"/api/deployments/{deployment_id}/knowledge-base", headers=auth(token), json={
            "name": "默认知识库",
            "documents": [{
                "title": "短文档",
                "content": "太短了",
                "doc_type": "faq",
            }],
        })
        assert short_res.status_code == 400
        assert "内容过短" in json.loads(short_res.data)["error"]

        first_res = client.post(f"/api/deployments/{deployment_id}/knowledge-base", headers=auth(token), json={
            "name": "默认知识库",
            "documents": [{
                "title": "退款政策 FAQ",
                "content": "退款审核通过后 1-3 个工作日原路退回，涉及争议场景需要人工复核。",
                "doc_type": "faq",
            }],
        })
        assert first_res.status_code == 201

        duplicate_res = client.post(f"/api/deployments/{deployment_id}/knowledge-base", headers=auth(token), json={
            "name": "默认知识库",
            "documents": [{
                "title": "退款政策 FAQ",
                "content": "这是一份重复标题的文档内容，用于验证知识库上传校验。",
                "doc_type": "faq",
            }],
        })
        assert duplicate_res.status_code == 400
        assert "已存在同名文档" in json.loads(duplicate_res.data)["error"]

    def test_reject_overlong_knowledge_document(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(client, app_module, db)
        too_long_content = "A" * 20001
        res = client.post(f"/api/deployments/{deployment_id}/knowledge-base", headers=auth(token), json={
            "name": "默认知识库",
            "documents": [{
                "title": "超长文档",
                "content": too_long_content,
                "doc_type": "faq",
            }],
        })
        assert res.status_code == 400
        assert "内容过长" in json.loads(res.data)["error"]

    def test_publish_detail_includes_knowledge_summary(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(client, app_module, db)
        client.post(f"/api/deployments/{deployment_id}/knowledge-base", headers=auth(token), json={
            "name": "售后 FAQ",
            "documents": [{
                "title": "退款政策 FAQ",
                "content": "退款审核通过后 1-3 个工作日原路退回，复杂争议会转人工处理。",
                "doc_type": "faq",
            }, {
                "title": "人工处理说明",
                "content": "涉及赔付、投诉、身份核验等高风险问题时，机器人必须转人工确认。",
                "doc_type": "policy",
            }],
        })

        publish_res = client.post(f"/api/deployments/{deployment_id}/publish", headers=auth(token))
        assert publish_res.status_code == 200

        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        assert detail_res.status_code == 200
        deployment = json.loads(detail_res.data)["deployment"]
        assert deployment["knowledge_version"].startswith("kb-")
        assert deployment["knowledge_last_published_at"] is not None
        assert deployment["knowledge_summary"]["knowledge_base_count"] == 1
        assert deployment["knowledge_summary"]["published_document_count"] == 2
        assert deployment["knowledge_summary"]["bases"][0]["sample_titles"][0] == "退款政策 FAQ"

    def test_update_deployment_config_and_list_audit_logs(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(client, app_module, db, publish=True)
        update_res = client.put(f"/api/deployments/{deployment_id}/config", headers=auth(token), json={
            "brand_voice": "warm",
            "forbidden_topics": ["退款"],
            "sensitive_keywords": ["赔偿"],
            "pii_masking_enabled": True,
            "provider": "dashscope",
            "provider_model": "qwen-max",
            "provider_temperature": 0.3,
            "provider_top_p": 0.85,
            "provider_max_tokens": 1024,
            "provider_timeout_seconds": 45,
            "provider_retry_attempts": 2,
            "allowed_origins": ["https://www.example.com"],
        })
        assert update_res.status_code == 200
        deployment = json.loads(update_res.data)["deployment"]
        assert deployment["config"]["brand_voice"] == "warm"
        assert deployment["config"]["forbidden_topics"] == ["退款"]
        assert deployment["config"]["provider"] == "dashscope"
        assert deployment["config"]["provider_model"] == "qwen-max"
        assert deployment["config"]["provider_max_tokens"] == 1024
        assert deployment["config"]["allowed_origins"] == ["https://www.example.com"]

        audit_res = client.get(f"/api/deployments/{deployment_id}/audit-logs", headers=auth(token))
        assert audit_res.status_code == 200
        audit_logs = json.loads(audit_res.data)["audit_logs"]
        assert any(log["action_type"] == "deployment.config_updated" for log in audit_logs)

    def test_reject_invalid_allowed_origins(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(client, app_module, db)
        update_res = client.put(f"/api/deployments/{deployment_id}/config", headers=auth(token), json={
            "allowed_origins": ["not-a-valid-origin"],
        })
        assert update_res.status_code == 400
        assert "来源域名格式无效" in json.loads(update_res.data)["error"]

    def test_public_token_controls_and_suspend_resume(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(client, app_module, db, publish=True)
        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        original_token = json.loads(detail_res.data)["deployment"]["public_token"]

        disable_res = client.post(f"/api/deployments/{deployment_id}/public-token/disable", headers=auth(token))
        assert disable_res.status_code == 200
        assert json.loads(disable_res.data)["deployment"]["config"]["public_access_enabled"] is False

        denied_res = client.post(f"/api/public/chat/{original_token}/message", json={
            "message": "你好",
            "visitor_name": "访客",
        })
        assert denied_res.status_code == 403
        assert "已停用" in json.loads(denied_res.data)["error"]

        enable_res = client.post(f"/api/deployments/{deployment_id}/public-token/enable", headers=auth(token))
        assert enable_res.status_code == 200
        assert json.loads(enable_res.data)["deployment"]["config"]["public_access_enabled"] is True

        rotate_res = client.post(f"/api/deployments/{deployment_id}/public-token/rotate", headers=auth(token))
        assert rotate_res.status_code == 200
        new_token = json.loads(rotate_res.data)["deployment"]["public_token"]
        assert new_token != original_token

        old_token_res = client.post(f"/api/public/chat/{original_token}/message", json={
            "message": "你好",
            "visitor_name": "访客",
        })
        assert old_token_res.status_code == 404

        suspend_res = client.post(f"/api/deployments/{deployment_id}/suspend", headers=auth(token))
        assert suspend_res.status_code == 200
        assert json.loads(suspend_res.data)["deployment"]["status"] == "suspended"

        suspended_res = client.post(f"/api/public/chat/{new_token}/message", json={
            "message": "你好",
            "visitor_name": "访客",
        })
        assert suspended_res.status_code == 403
        assert "已暂停" in json.loads(suspended_res.data)["error"]

        resume_res = client.post(f"/api/deployments/{deployment_id}/resume", headers=auth(token))
        assert resume_res.status_code == 200
        assert json.loads(resume_res.data)["deployment"]["status"] == "active"


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
        source_refs = json.loads(chat_res.data)["assistant_message"]["source_refs"]
        assert "system_prompt" not in source_refs
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

    def test_public_chat_browser_origin_requires_allowed_origin(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="退款政策会在 1-3 个工作日内处理完成。",
            config={"allowed_origins": ["https://www.example.com"]},
        )
        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        public_token = json.loads(detail_res.data)["deployment"]["public_token"]

        denied_res = client.post(
            f"/api/public/chat/{public_token}/message",
            headers={"Origin": "https://evil.example"},
            json={"message": "退款多久处理？", "visitor_name": "访客"},
        )
        assert denied_res.status_code == 403
        assert "未被授权" in json.loads(denied_res.data)["error"]

        allow_res = client.post(
            f"/api/public/chat/{public_token}/message",
            headers={
                "Origin": "https://www.example.com",
                "Referer": "https://www.example.com/support",
            },
            json={"message": "退款多久处理？", "visitor_name": "访客"},
        )
        assert allow_res.status_code == 200
        assert "1-3" in json.loads(allow_res.data)["assistant_message"]["content"]

    def test_public_chat_browser_without_whitelist_is_denied(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="这里是基础 FAQ。",
        )
        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        public_token = json.loads(detail_res.data)["deployment"]["public_token"]

        denied_res = client.post(
            f"/api/public/chat/{public_token}/message",
            headers={"Origin": "https://widget.example.com"},
            json={"message": "你好", "visitor_name": "访客"},
        )
        assert denied_res.status_code == 403
        assert "尚未配置允许访问的浏览器域名" in json.loads(denied_res.data)["error"]

    def test_public_chat_server_side_call_can_skip_origin_whitelist(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="我们支持 7x24 在线客服。",
        )
        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        public_token = json.loads(detail_res.data)["deployment"]["public_token"]

        chat_res = client.post(
            f"/api/public/chat/{public_token}/message",
            headers={"User-Agent": "server-to-server-client/1.0"},
            json={"message": "你们支持在线客服吗？", "visitor_name": "服务端调用"},
        )
        assert chat_res.status_code == 200
        assert "在线客服" in json.loads(chat_res.data)["assistant_message"]["content"]

    def test_public_chat_denied_origin_records_audit(self, client, app_module, db):
        token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="我们支持 7x24 在线客服。",
            config={"allowed_origins": ["https://www.example.com"]},
        )
        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        public_token = json.loads(detail_res.data)["deployment"]["public_token"]

        denied_res = client.post(
            f"/api/public/chat/{public_token}/message",
            headers={
                "Origin": "https://evil.example",
                "Referer": "https://evil.example/chat",
                "User-Agent": "evil-widget/1.0",
            },
            json={"message": "你好", "visitor_name": "访客"},
        )
        assert denied_res.status_code == 403

        audit_res = client.get(f"/api/deployments/{deployment_id}/audit-logs", headers=auth(token))
        audit_logs = json.loads(audit_res.data)["audit_logs"]
        denial_log = next(log for log in audit_logs if log["action_type"] == "chat.public_access_denied")
        assert denial_log["details"]["reason"] == "origin_not_allowed"
        assert denial_log["details"]["access_details"]["origin"] == "https://evil.example"
        assert denial_log["details"]["access_details"]["user_agent"] == "evil-widget/1.0"

    def test_public_chat_rate_limit_and_quota_guardrails(self, client, app_module, db):
        token, deployment_id, _, plan = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="这里是套餐知识库。",
            config={"allowed_origins": ["https://www.example.com"]},
        )
        plan.included_conversations = 1
        db.session.commit()
        app_module.app.config["PUBLIC_CHAT_IP_LIMIT_PER_MINUTE"] = 1
        app_module.app.config["PUBLIC_CHAT_DEPLOYMENT_LIMIT_PER_MINUTE"] = 1

        detail_res = client.get(f"/api/deployments/{deployment_id}", headers=auth(token))
        public_token = json.loads(detail_res.data)["deployment"]["public_token"]

        first_res = client.post(
            f"/api/public/chat/{public_token}/message",
            headers={"Origin": "https://www.example.com"},
            json={"message": "第一条", "visitor_name": "访客"},
        )
        assert first_res.status_code == 200

        limited_res = client.post(
            f"/api/public/chat/{public_token}/message",
            headers={"Origin": "https://www.example.com"},
            json={"message": "第二条", "visitor_name": "访客"},
        )
        assert limited_res.status_code == 429
        assert "频繁" in json.loads(limited_res.data)["error"]

        from services.public_api_service import reset_public_api_rate_limits
        reset_public_api_rate_limits()
        app_module.app.config["PUBLIC_CHAT_IP_LIMIT_PER_MINUTE"] = 9999
        app_module.app.config["PUBLIC_CHAT_DEPLOYMENT_LIMIT_PER_MINUTE"] = 9999

        quota_res = client.post(
            f"/api/public/chat/{public_token}/message",
            headers={"Origin": "https://www.example.com"},
            json={"message": "第三条", "visitor_name": "访客"},
        )
        assert quota_res.status_code == 403
        assert "额度已用尽" in json.loads(quota_res.data)["error"]

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

    def test_chat_without_knowledge_hit_uses_explicit_reason(self, client, app_module, db):
        _, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="这里仅包含营业时间和客服电话。",
        )

        chat_res = client.post(f"/api/chat/{deployment_id}/message", json={
            "message": "请问你们的退款规则和赔付细则是什么？",
            "visitor_name": "访客 Z",
        })
        assert chat_res.status_code == 200
        chat_data = json.loads(chat_res.data)
        assert "当前知识库没有命中" in chat_data["assistant_message"]["content"]
        assert chat_data["handoff_ticket"]["reason"] == "knowledge_not_found"
        assert chat_data["assistant_message"]["source_refs"]["response_reason"] == "knowledge_not_found"

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

    def test_chat_with_dashscope_provider_records_provider_meta(self, client, app_module, db, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
        monkeypatch.setenv("DASHSCOPE_MODEL", "qwen-max")

        from services import provider_service

        class FakeDashScopeResponse:
            def __init__(self, payload):
                self.payload = payload

            def read(self):
                return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_urlopen(request_obj, timeout=0):
            payload = json.loads(request_obj.data.decode("utf-8"))
            assert payload["model"] == "qwen-max"
            return FakeDashScopeResponse({
                "id": "chatcmpl-test-001",
                "choices": [{
                    "message": {"content": "您好，这里是 Qwen Max 的回复。"},
                    "finish_reason": "stop",
                }],
                "usage": {
                    "prompt_tokens": 128,
                    "completion_tokens": 32,
                    "total_tokens": 160,
                },
            })

        monkeypatch.setattr(provider_service.urllib.request, "urlopen", fake_urlopen)

        token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="退款审核通过后 1-3 个工作日原路退回。",
            config={
                "provider": "dashscope",
                "provider_model": "qwen-max",
            },
        )

        chat_res = client.post(f"/api/chat/{deployment_id}/message", json={
            "message": "退款大概多久到账？",
            "visitor_name": "控制台访客",
        })
        assert chat_res.status_code == 200
        chat_data = json.loads(chat_res.data)
        assert chat_data["assistant_message"]["content"] == "您好，这里是 Qwen Max 的回复。"
        source_refs = chat_data["assistant_message"]["source_refs"]
        assert source_refs["provider"] == "dashscope"
        assert source_refs["provider_meta"]["model"] == "qwen-max"
        assert source_refs["provider_meta"]["status"] == "ok"
        assert source_refs["provider_meta"]["fallback_used"] is False
        assert "system_prompt" not in source_refs

        audit_res = client.get(f"/api/deployments/{deployment_id}/audit-logs", headers=auth(token))
        audit_logs = json.loads(audit_res.data)["audit_logs"]
        chat_log = next(log for log in audit_logs if log["action_type"] == "chat.turn")
        assert chat_log["details"]["provider_meta"]["status"] == "ok"
        assert chat_log["details"]["provider_meta"]["request_id"] == "chatcmpl-test-001"

    def test_chat_falls_back_to_rules_when_dashscope_fails(self, client, app_module, db, monkeypatch):
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
        monkeypatch.setenv("DASHSCOPE_MODEL", "qwen-max")

        from services import provider_service

        def fake_urlopen(_request_obj, timeout=0):
            raise RuntimeError("dashscope timeout")

        monkeypatch.setattr(provider_service.urllib.request, "urlopen", fake_urlopen)

        token, deployment_id, _, _ = create_agent_deployment(
            client,
            app_module,
            db,
            publish=True,
            knowledge_content="我们支持 7x24 在线客服，复杂问题会转人工继续处理。",
            config={
                "provider": "dashscope",
                "provider_model": "qwen-max",
            },
        )

        chat_res = client.post(f"/api/chat/{deployment_id}/message", json={
            "message": "你们支持7x24在线吗？",
            "visitor_name": "控制台访客",
        })
        assert chat_res.status_code == 200
        chat_data = json.loads(chat_res.data)
        assert "7x24" in chat_data["assistant_message"]["content"]
        source_refs = chat_data["assistant_message"]["source_refs"]
        assert source_refs["provider"] == "rules"
        assert source_refs["provider_meta"]["model"] == "rules"
        assert source_refs["provider_meta"]["status"] == "provider_failed"
        assert source_refs["provider_meta"]["fallback_used"] is True

        audit_res = client.get(f"/api/deployments/{deployment_id}/audit-logs", headers=auth(token))
        audit_logs = json.loads(audit_res.data)["audit_logs"]
        chat_log = next(log for log in audit_logs if log["action_type"] == "chat.turn")
        assert chat_log["details"]["provider_meta"]["status"] == "provider_failed"
        assert chat_log["details"]["provider_meta"]["requested_provider"] == "dashscope"


class TestOfficialAgentFlows:
    def test_support_responder_official_flow_from_search_to_public_api(self, client, app_module, db):
        bootstrap_official_agents(app_module, db)
        search_res = client.get("/api/workers?worker_type=agent_service&keyword=客服")
        assert search_res.status_code == 200
        workers = json.loads(search_res.data)["workers"]
        worker = next(item for item in workers if item["template_key"] == "support_responder")

        detail_res = client.get(f"/api/workers/{worker['id']}")
        assert detail_res.status_code == 200
        detail = json.loads(detail_res.data)["worker"]
        starter_plan = next(plan for plan in detail["service_plans"] if plan["slug"] == "starter")

        register(client, "official1", "official1@t.com")
        token = login(client, "official1")
        _, public_token = buy_publish_and_get_token(
            client,
            token,
            detail["id"],
            starter_plan["id"],
            "我们支持 7x24 在线答复，复杂问题会转人工继续处理。",
            channel_type="web_widget",
        )

        api_res = client.post(f"/api/public/chat/{public_token}/message", json={
            "message": "你们支持7x24在线吗？",
            "visitor_name": "流程验证用户",
        })
        assert api_res.status_code == 200
        api_data = json.loads(api_res.data)
        assert "7x24" in api_data["assistant_message"]["content"]

    def test_internal_official_agent_is_hidden_from_public_marketplace(self, client, app_module, db):
        bootstrap_official_agents(app_module, db)
        search_res = client.get("/api/workers?worker_type=agent_service")
        assert search_res.status_code == 200
        workers = json.loads(search_res.data)["workers"]
        assert any(item["template_key"] == "support_responder" for item in workers)
        assert all(item["template_key"] != "wechat_official_account_manager" for item in workers)

        worker = app_module.Worker.query.filter_by(template_key="wechat_official_account_manager").first()
        assert worker is not None

        detail_res = client.get(f"/api/workers/{worker.id}")
        assert detail_res.status_code == 200
        detail = json.loads(detail_res.data)["worker"]
        assert detail["template_key"] == "wechat_official_account_manager"
        assert detail["launch_stage"] == "internal"

    def test_kongkong_official_flow_from_search_to_launch_link(self, client, app_module, db):
        bootstrap_official_agents(app_module, db)
        search_res = client.get("/api/workers?worker_type=agent_service&keyword=空空")
        assert search_res.status_code == 200
        workers = json.loads(search_res.data)["workers"]
        worker = next(item for item in workers if item["runtime_kind"] == "openclaw_managed")

        detail_res = client.get(f"/api/workers/{worker['id']}")
        assert detail_res.status_code == 200
        detail = json.loads(detail_res.data)["worker"]
        monthly_plan = next(plan for plan in detail["service_plans"] if plan["slug"] == "monthly")
        hourly_plan = next(plan for plan in detail["service_plans"] if plan["slug"] == "hourly")
        assert monthly_plan["price"] == 99.0
        assert hourly_plan["price"] == 2.0

        register(client, "kong1", "kong1@t.com")
        token = login(client, "kong1")
        order_res = client.post("/api/orders", headers=auth(token), json={
            "worker_id": detail["id"],
            "service_plan_id": hourly_plan["id"],
            "duration_hours": 5,
        })
        assert order_res.status_code == 201
        order = json.loads(order_res.data)["order"]
        assert order["total_amount"] == 10.0

        client.post(f"/api/orders/{order['id']}/pay", headers=auth(token))
        deployment_res = client.post(f"/api/orders/{order['id']}/deployments", headers=auth(token), json={
            "deployment_name": "空空工作台",
            "channel_type": "workspace",
        })
        assert deployment_res.status_code == 201
        deployment = json.loads(deployment_res.data)["deployment"]
        assert deployment["kongkong_instance"]["status"] == "running"

        launch_res = client.post(
            f"/api/kongkong/instances/{deployment['kongkong_instance']['id']}/launch-link",
            headers=auth(token),
        )
        assert launch_res.status_code == 200
        launch = json.loads(launch_res.data)["launch"]
        assert launch["launch_url"].endswith("/kongkong/mock/kongkong-1/")
        assert launch["gateway_token"]


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

    def test_runtime_config(self, client):
        r = client.get("/api/runtime-config")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["payment_mode"] in ("mock", "manual_review")

    def test_runtime_config_exposes_dashscope_provider_defaults(self, client, monkeypatch):
        monkeypatch.delenv("AGENT_PROVIDER", raising=False)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")
        monkeypatch.setenv("DASHSCOPE_MODEL", "qwen-max")

        r = client.get("/api/runtime-config")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["provider"]["default_provider"] == "dashscope"
        assert data["provider"]["default_model"] == "qwen-max"
        assert data["provider"]["dashscope_enabled"] is True
        assert data["provider"]["provider_defaults"]["provider"] == "dashscope"

    def test_api_docs(self, client):
        r = client.get("/api/docs")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "openapi" in data
        assert "paths" in data

    def test_rate_limiter_loaded(self, app_module):
        assert hasattr(app_module, "limiter")

    def test_validate_runtime_config_rejects_production_defaults(self, app_module):
        with pytest.raises(RuntimeError):
            app_module.validate_runtime_config(app_env="production", env_map={})

    def test_validate_runtime_config_accepts_production_secrets(self, app_module):
        assert app_module.validate_runtime_config(app_env="production", env_map={
            "DB_PASS": "prod-db-pass-123456",
            "JWT_SECRET": "prod-jwt-secret-abcdefghijklmnopqrstuvwxyz",
            "PUBLIC_BASE_URL": "https://app.xiaxia.factory",
            "ALLOWED_ORIGINS": "https://app.xiaxia.factory,https://admin.xiaxia.factory",
        }) is True

    def test_bootstrap_initial_admin_creates_admin_in_production(self, client, app_module, db):
        assert app_module.User.query.filter_by(role="admin").count() == 0
        admin = app_module.ensure_initial_admin_account(app_env="production", env_map={
            "ADMIN_INIT_USERNAME": "founder",
            "ADMIN_INIT_EMAIL": "founder@xiaxia.factory",
            "ADMIN_INIT_PASSWORD": "FounderPass1234",
        })
        db.session.commit()

        assert admin is not None
        created = app_module.User.query.filter_by(username="founder").first()
        assert created is not None
        assert created.role == "admin"

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
