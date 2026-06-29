"""
app/retrieval/filters.py — Build Chroma/BM25 filter dicts from request parameters and user ACL.
"""

from __future__ import annotations

from typing import Any


def build_chroma_where(
    user_role: str = "employee",
    department: str | None = None,
    document_type: str | None = None,
    author: str | None = None,
    tags: list[str] | None = None,
    policy_version: str | None = None,
    uploaded_after: str | None = None,
    content_types: list[str] | None = None,
    filter_department: str | None = None,
) -> dict[str, Any] | None:
    """
    Build a Chroma `where` filter dict.

    ACL: Only return chunks the user has access to.
    All other filters are optional.
    """
    conditions: list[dict[str, Any]] = []

    # Department ACL/filter
    if user_role == "admin":
        if filter_department:
            conditions.append({"department": {"$eq": filter_department}})
    else:
        allowed_depts = ["general"]
        if department and department != "general":
            allowed_depts.append(department)

        if filter_department:
            if filter_department in allowed_depts:
                conditions.append({"department": {"$eq": filter_department}})
            else:
                conditions.append({"department": {"$eq": "__unauthorized__"}})
        else:
            if len(allowed_depts) == 1:
                conditions.append({"department": {"$eq": allowed_depts[0]}})
            else:
                conditions.append({"department": {"$in": allowed_depts}})

    if document_type:
        conditions.append({"document_type": {"$eq": document_type}})

    if author:
        conditions.append({"author": {"$eq": author}})

    if policy_version:
        conditions.append({"policy_version": {"$eq": policy_version}})

    if content_types:
        conditions.append({"content_type": {"$in": content_types}})

    if uploaded_after:
        conditions.append({"uploaded_at": {"$gte": uploaded_after}})

    if len(conditions) == 1:
        return conditions[0]
    elif len(conditions) > 1:
        return {"$and": conditions}
    return None


def build_bm25_where(
    user_role: str = "employee",
    department: str | None = None,
    content_types: list[str] | None = None,
    filter_department: str | None = None,
    document_type: str | None = None,
    author: str | None = None,
    policy_version: str | None = None,
) -> dict[str, Any]:
    """Build filter dictionary for BM25."""
    where: dict[str, Any] = {}

    if user_role != "admin":
        where["access_roles"] = {"$contains": user_role}

    # Department ACL/filter
    if user_role == "admin":
        if filter_department:
            where["department"] = {"$eq": filter_department}
    else:
        allowed_depts = ["general"]
        if department and department != "general":
            allowed_depts.append(department)

        if filter_department:
            if filter_department in allowed_depts:
                where["department"] = {"$eq": filter_department}
            else:
                where["department"] = {"$eq": "__unauthorized__"}
        else:
            if len(allowed_depts) == 1:
                where["department"] = {"$eq": allowed_depts[0]}
            else:
                where["department"] = {"$in": allowed_depts}

    if document_type:
        where["document_type"] = {"$eq": document_type}

    if author:
        where["author"] = {"$eq": author}

    if policy_version:
        where["policy_version"] = {"$eq": policy_version}

    if content_types:
        where["content_type"] = {"$in": content_types}

    return where


def acl_hash(user_role: str, department: str) -> str:
    """Stable hash of user permissions — used as part of cache keys."""
    import hashlib

    return hashlib.sha256(f"{user_role}::{department}".encode()).hexdigest()[:16]
