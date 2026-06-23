from app.services.copilot.access_scope import (
    AccessScope,
    HierarchyScopeFilter,
    append_merchant_scope,
    append_transaction_scope,
    scoped_merchant_id_subquery,
)


def test_merchant_scope_org_only():
    scope = AccessScope(organization_id="org-11111111-1111-1111-1111-111111111111")
    where = append_merchant_scope("", scope)
    assert "organization_id = 'org-11111111-1111-1111-1111-111111111111'" in where


def test_merchant_scope_with_hierarchy():
    scope = AccessScope(
        organization_id="org-11111111-1111-1111-1111-111111111111",
        hierarchy_enabled=True,
        hierarchy_filter=HierarchyScopeFilter(
            column="branch_office_id",
            taxonomy_id="tax-22222222-2222-2222-2222-222222222222",
        ),
    )
    where = append_merchant_scope("", scope)
    assert "branch_office_id = 'tax-22222222-2222-2222-2222-222222222222'" in where


def test_transaction_scope_uses_merchant_subquery():
    scope = AccessScope(organization_id="org-11111111-1111-1111-1111-111111111111")
    where = append_transaction_scope("", scope)
    assert "merchant_id IN" in where
    assert scoped_merchant_id_subquery(scope) in where
