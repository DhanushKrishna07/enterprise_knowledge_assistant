from app.retrieval.filters import build_bm25_where, build_chroma_where


def test_admin_no_filter():
    # Admin should have no access restrictions
    where_chroma = build_chroma_where(user_role="admin", department="general")
    assert where_chroma is None

    where_bm25 = build_bm25_where(user_role="admin", department="general")
    assert "access_roles" not in where_bm25
    assert "department" not in where_bm25


def test_admin_with_filter():
    # Admin with explicit filter
    where_chroma = build_chroma_where(
        user_role="admin", department="general", filter_department="hr"
    )
    assert where_chroma == {"department": {"$eq": "hr"}}

    where_bm25 = build_bm25_where(user_role="admin", department="general", filter_department="hr")
    assert where_bm25["department"] == {"$eq": "hr"}


def test_employee_no_filter():
    # Regular employee should see only general documents
    where_chroma = build_chroma_where(user_role="employee", department="general")
    assert where_chroma == {"department": {"$eq": "general"}}

    where_bm25 = build_bm25_where(user_role="employee", department="general")
    assert where_bm25["access_roles"] == {"$contains": "employee"}
    assert where_bm25["department"] == {"$eq": "general"}


def test_employee_with_authorized_filter():
    # Employee explicitly filtering for general
    where_chroma = build_chroma_where(
        user_role="employee", department="general", filter_department="general"
    )
    assert where_chroma == {"department": {"$eq": "general"}}

    where_bm25 = build_bm25_where(
        user_role="employee", department="general", filter_department="general"
    )
    assert where_bm25["department"] == {"$eq": "general"}


def test_employee_with_unauthorized_filter():
    # Employee filtering for hr should be unauthorized (dummy match to return 0 results)
    where_chroma = build_chroma_where(
        user_role="employee", department="general", filter_department="hr"
    )
    assert where_chroma == {"department": {"$eq": "__unauthorized__"}}

    where_bm25 = build_bm25_where(
        user_role="employee", department="general", filter_department="hr"
    )
    assert where_bm25["department"] == {"$eq": "__unauthorized__"}


def test_hr_employee_no_filter():
    # HR employee should see general and hr documents
    where_chroma = build_chroma_where(user_role="employee", department="hr")
    assert where_chroma == {"department": {"$in": ["general", "hr"]}}

    where_bm25 = build_bm25_where(user_role="employee", department="hr")
    assert where_bm25["access_roles"] == {"$contains": "employee"}
    assert where_bm25["department"] == {"$in": ["general", "hr"]}


def test_hr_employee_with_authorized_filter():
    # HR employee explicitly filtering for hr
    where_chroma = build_chroma_where(user_role="employee", department="hr", filter_department="hr")
    assert where_chroma == {"department": {"$eq": "hr"}}

    where_bm25 = build_bm25_where(user_role="employee", department="hr", filter_department="hr")
    assert where_bm25["department"] == {"$eq": "hr"}


def test_hr_employee_with_unauthorized_filter():
    # HR employee filtering for it should be unauthorized
    where_chroma = build_chroma_where(user_role="employee", department="hr", filter_department="it")
    assert where_chroma == {"department": {"$eq": "__unauthorized__"}}

    where_bm25 = build_bm25_where(user_role="employee", department="hr", filter_department="it")
    assert where_bm25["department"] == {"$eq": "__unauthorized__"}
