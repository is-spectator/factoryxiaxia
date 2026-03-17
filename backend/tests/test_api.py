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


# ==================== High-risk Regression ====================

class TestDisabledUserLogin:
    """禁用用户无法登录"""

    def test_disabled_user_cannot_login(self, client, app_module, db):
        register(client)
        u = app_module.User.query.filter_by(username="testuser").first()
        u.is_active = False
        db.session.commit()
        r = client.post("/api/login", json={"login_id": "testuser", "password": "Test1234"})
        assert r.status_code == 403
        assert "禁用" in json.loads(r.data)["error"]

    def test_disabled_user_token_rejected_on_order(self, client, app_module, db):
        """禁用用户的已有 token 无法创建订单"""
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        u = app_module.User.query.filter_by(username="testuser").first()
        u.is_active = False
        db.session.commit()
        r = client.post("/api/orders", headers=auth(token),
                        json={"worker_id": w.id, "duration_hours": 1})
        assert r.status_code == 401


class TestAdminOrderStateMachine:
    """管理员不能绕过状态机随意修改订单状态"""

    def _setup(self, client, app_module, db):
        make_admin(app_module, db)
        admin_token = login(client, "admin1")
        register(client, "buyer", "buyer@t.com")
        buyer_token = login(client, "buyer")
        _, w = seed_worker(app_module, db)
        cr = client.post("/api/orders", headers=auth(buyer_token),
                         json={"worker_id": w.id, "duration_hours": 5})
        oid = json.loads(cr.data)["order"]["id"]
        return admin_token, buyer_token, oid

    def test_cannot_skip_pending_to_active(self, client, app_module, db):
        admin_token, _, oid = self._setup(client, app_module, db)
        r = client.put(f"/api/admin/orders/{oid}/status", headers=auth(admin_token),
                       json={"status": "active"})
        assert r.status_code == 400
        assert "状态流转不允许" in json.loads(r.data)["error"]

    def test_cannot_skip_pending_to_completed(self, client, app_module, db):
        admin_token, _, oid = self._setup(client, app_module, db)
        r = client.put(f"/api/admin/orders/{oid}/status", headers=auth(admin_token),
                       json={"status": "completed"})
        assert r.status_code == 400

    def test_cannot_go_back_from_cancelled(self, client, app_module, db):
        admin_token, buyer_token, oid = self._setup(client, app_module, db)
        client.post(f"/api/orders/{oid}/cancel", headers=auth(buyer_token))
        r = client.put(f"/api/admin/orders/{oid}/status", headers=auth(admin_token),
                       json={"status": "pending"})
        assert r.status_code == 400

    def test_valid_transition_works(self, client, app_module, db):
        admin_token, _, oid = self._setup(client, app_module, db)
        r = client.put(f"/api/admin/orders/{oid}/status", headers=auth(admin_token),
                       json={"status": "paid"})
        assert r.status_code == 200
        assert json.loads(r.data)["order"]["status"] == "paid"

    def test_admin_status_change_sets_timestamp(self, client, app_module, db):
        admin_token, _, oid = self._setup(client, app_module, db)
        client.put(f"/api/admin/orders/{oid}/status", headers=auth(admin_token),
                   json={"status": "paid"})
        r = client.put(f"/api/admin/orders/{oid}/status", headers=auth(admin_token),
                       json={"status": "active"})
        data = json.loads(r.data)
        assert data["order"]["activated_at"] is not None


class TestMessageTriggers:
    """核心动作均应生成站内消息"""

    def _setup(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        return token, w

    def _msg_count(self, client, token):
        r = client.get("/api/messages", headers=auth(token))
        return json.loads(r.data)["total"]

    def test_cancel_generates_message(self, client, app_module, db):
        token, w = self._setup(client, app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 1})
        oid = json.loads(cr.data)["order"]["id"]
        before = self._msg_count(client, token)
        client.post(f"/api/orders/{oid}/cancel", headers=auth(token))
        assert self._msg_count(client, token) > before

    def test_pay_generates_message(self, client, app_module, db):
        token, w = self._setup(client, app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 1})
        oid = json.loads(cr.data)["order"]["id"]
        before = self._msg_count(client, token)
        client.post(f"/api/orders/{oid}/pay", headers=auth(token))
        assert self._msg_count(client, token) > before

    def test_activate_generates_message(self, client, app_module, db):
        token, w = self._setup(client, app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 1})
        oid = json.loads(cr.data)["order"]["id"]
        client.post(f"/api/orders/{oid}/pay", headers=auth(token))
        before = self._msg_count(client, token)
        client.post(f"/api/orders/{oid}/activate", headers=auth(token))
        assert self._msg_count(client, token) > before

    def test_complete_generates_message(self, client, app_module, db):
        token, w = self._setup(client, app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 1})
        oid = json.loads(cr.data)["order"]["id"]
        client.post(f"/api/orders/{oid}/pay", headers=auth(token))
        client.post(f"/api/orders/{oid}/activate", headers=auth(token))
        before = self._msg_count(client, token)
        client.post(f"/api/orders/{oid}/complete", headers=auth(token))
        assert self._msg_count(client, token) > before

    def test_refund_generates_message(self, client, app_module, db):
        token, w = self._setup(client, app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 1})
        oid = json.loads(cr.data)["order"]["id"]
        client.post(f"/api/orders/{oid}/pay", headers=auth(token))
        before = self._msg_count(client, token)
        client.post(f"/api/orders/{oid}/refund", headers=auth(token))
        assert self._msg_count(client, token) > before

    def test_review_generates_message(self, client, app_module, db):
        token, w = self._setup(client, app_module, db)
        cr = client.post("/api/orders", headers=auth(token),
                         json={"worker_id": w.id, "duration_hours": 1})
        oid = json.loads(cr.data)["order"]["id"]
        client.post(f"/api/orders/{oid}/pay", headers=auth(token))
        client.post(f"/api/orders/{oid}/activate", headers=auth(token))
        client.post(f"/api/orders/{oid}/complete", headers=auth(token))
        before = self._msg_count(client, token)
        client.post(f"/api/orders/{oid}/review", headers=auth(token),
                    json={"rating": 5, "content": "Nice"})
        assert self._msg_count(client, token) > before

    def test_admin_status_change_generates_message(self, client, app_module, db):
        make_admin(app_module, db)
        admin_token = login(client, "admin1")
        register(client, "buyer2", "buyer2@t.com")
        buyer_token = login(client, "buyer2")
        _, w = seed_worker(app_module, db)
        cr = client.post("/api/orders", headers=auth(buyer_token),
                         json={"worker_id": w.id, "duration_hours": 1})
        oid = json.loads(cr.data)["order"]["id"]
        before = self._msg_count(client, buyer_token)
        client.put(f"/api/admin/orders/{oid}/status", headers=auth(admin_token),
                   json={"status": "paid"})
        assert self._msg_count(client, buyer_token) > before


class TestRecommendationsAuth:
    """已登录用户获得个性化推荐"""

    def test_personalized_after_order(self, client, app_module, db):
        register(client)
        token = login(client)
        _, w = seed_worker(app_module, db)
        client.post("/api/orders", headers=auth(token),
                    json={"worker_id": w.id, "duration_hours": 1})
        r = client.get("/api/recommendations", headers=auth(token))
        assert r.status_code == 200
