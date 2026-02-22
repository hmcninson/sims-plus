## Description
<!-- What does this PR do? -->

## Type of Change
- [ ] Feature
- [ ] Bug fix
- [ ] Refactor
- [ ] Security fix
- [ ] Documentation

## Multi-Tenancy Security Checklist
- [ ] All new queries filter by `tenant_id`
- [ ] No raw SQL outside of migrations
- [ ] RLS policies added for any new tables (USING + WITH CHECK, FOR ALL TO sims_app_user)
- [ ] No `from __future__ import annotations` in endpoint files
- [ ] Tests run as `sims_app_user`, not postgres superuser
- [ ] Redis cache keys prefixed with `tenant:{tenant_id}:`
- [ ] New tables use TenantMixin + SoftDeleteMixin
- [ ] New tables imported in `db/base.py`
- [ ] Service layer uses flush()+refresh(), never commit()

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All existing tests pass
