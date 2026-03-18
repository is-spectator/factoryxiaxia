"""分类、员工列表、员工详情、评价、推荐路由"""
from flask import Blueprint, request, jsonify
from extensions import db
from models import Category, Worker, Review, Order, AgentTemplate
from utils.auth import get_current_user

bp = Blueprint("catalog", __name__)


@bp.route("/api/categories", methods=["GET"])
def get_categories():
    cats = Category.query.order_by(Category.sort_order).all()
    return jsonify({"categories": [c.to_dict() for c in cats]}), 200


@bp.route("/api/workers", methods=["GET"])
def get_workers():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 12, type=int)
    per_page = min(per_page, 50)

    category_id = request.args.get("category_id", type=int)
    status = request.args.get("status", type=str)
    keyword = request.args.get("keyword", "", type=str).strip()
    sort_by = request.args.get("sort_by", "total_orders", type=str)

    query = Worker.query

    if category_id:
        query = query.filter(Worker.category_id == category_id)
    if status:
        query = query.filter(Worker.status == status)
    if keyword:
        like_kw = f"%{keyword}%"
        query = query.filter(
            db.or_(
                Worker.name.like(like_kw),
                Worker.skills.like(like_kw),
                Worker.description.like(like_kw),
            )
        )

    if sort_by == "price_asc":
        query = query.order_by(Worker.hourly_rate.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Worker.hourly_rate.desc())
    elif sort_by == "rating":
        query = query.order_by(Worker.rating.desc())
    elif sort_by == "level":
        query = query.order_by(Worker.level.desc())
    else:
        query = query.order_by(Worker.total_orders.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "workers": [w.to_brief_dict() for w in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/workers/<int:worker_id>", methods=["GET"])
def get_worker_detail(worker_id):
    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "数字员工不存在"}), 404
    worker_data = worker.to_dict()
    if worker.template_key:
        template = AgentTemplate.query.filter_by(key=worker.template_key).first()
        worker_data["agent_template"] = template.to_dict() if template else None
    else:
        worker_data["agent_template"] = None
    return jsonify({"worker": worker_data}), 200


@bp.route("/api/workers/<int:worker_id>/reviews", methods=["GET"])
def get_worker_reviews(worker_id):
    worker = Worker.query.get(worker_id)
    if not worker:
        return jsonify({"error": "员工不存在"}), 404

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    per_page = min(per_page, 50)

    query = Review.query.filter_by(worker_id=worker_id).order_by(Review.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "reviews": [r.to_dict() for r in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    }), 200


@bp.route("/api/recommendations", methods=["GET"])
def get_recommendations():
    """基于用户历史订单推荐相似分类员工"""
    user = get_current_user()
    limit = request.args.get("limit", 6, type=int)
    limit = min(limit, 20)

    if user:
        ordered_cats = db.session.query(Worker.category_id).join(
            Order, Order.worker_id == Worker.id
        ).filter(Order.user_id == user.id).distinct().all()
        cat_ids = [c[0] for c in ordered_cats]

        ordered_worker_ids = db.session.query(Order.worker_id).filter(
            Order.user_id == user.id
        ).distinct().all()
        exclude_ids = [w[0] for w in ordered_worker_ids]

        if cat_ids:
            query = Worker.query.filter(
                Worker.category_id.in_(cat_ids),
                Worker.status != "offline",
            )
            if exclude_ids:
                query = query.filter(~Worker.id.in_(exclude_ids))
            recs = query.order_by(Worker.rating.desc(), Worker.total_orders.desc()).limit(limit).all()

            if len(recs) < limit:
                existing_ids = [w.id for w in recs] + exclude_ids
                extra = Worker.query.filter(
                    Worker.status != "offline",
                    ~Worker.id.in_(existing_ids) if existing_ids else True,
                ).order_by(Worker.total_orders.desc()).limit(limit - len(recs)).all()
                recs.extend(extra)

            return jsonify({"recommendations": [w.to_brief_dict() for w in recs], "strategy": "personalized"}), 200

    hot = Worker.query.filter(Worker.status != "offline").order_by(
        Worker.total_orders.desc(), Worker.rating.desc()
    ).limit(limit).all()
    return jsonify({"recommendations": [w.to_brief_dict() for w in hot], "strategy": "popular"}), 200
