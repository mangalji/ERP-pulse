# ERP Pulse — Review Checklist

## Purpose

Every implementation must pass this checklist before it is considered complete.

The goal is to maintain clean architecture, avoid technical debt, and keep the project consistent throughout development.

---

# 1. Scope Review

- [ ] Only the approved task/day was implemented.
- [ ] No future sprint functionality was added.
- [ ] No unnecessary features were introduced.
- [ ] No over-engineering.

---

# 2. Architecture Review

- [ ] Project architecture remains consistent.
- [ ] Business logic is not placed inside views.
- [ ] Views only handle request validation and responses.
- [ ] Services contain business logic.
- [ ] Repositories only perform database operations.
- [ ] No direct database queries inside views.
- [ ] No direct NetSuite calls outside the integrations module.

---

# 3. Code Quality

- [ ] PEP 8 followed.
- [ ] Meaningful variable names.
- [ ] Functions remain small and focused.
- [ ] No duplicate logic.
- [ ] No unnecessary comments.
- [ ] Comments explain WHY, not WHAT.

---

# 4. Security

- [ ] No secrets are hardcoded.
- [ ] .env is ignored by Git.
- [ ] .env.example contains placeholders only.
- [ ] Sensitive data is never committed.

---

# 5. Git Hygiene

- [ ] .gitignore is correct.
- [ ] __pycache__ is ignored.
- [ ] SQLite database is ignored.
- [ ] Virtual environment is ignored.
- [ ] node_modules is ignored.

---

# 6. Backend Verification

- [ ] python manage.py check passes.
- [ ] python manage.py migrate succeeds.
- [ ] python manage.py runserver starts successfully.
- [ ] No startup warnings.
- [ ] No unnecessary dependencies added.

---

# 7. Frontend Verification

- [ ] npm install succeeds.
- [ ] npm run dev works.
- [ ] No console errors.
- [ ] Folder structure follows project standards.

---

# 8. API Review

- [ ] API naming is consistent.
- [ ] URLs follow REST conventions.
- [ ] Proper HTTP methods are used.
- [ ] Validation exists where required.
- [ ] Consistent response structure.

---

# 9. Database Review

- [ ] Models are normalized.
- [ ] No duplicate tables.
- [ ] Proper relationships.
- [ ] Migrations generated correctly.
- [ ] No unnecessary fields.

---

# 10. AI Review (Future)

- [ ] AI never calculates business metrics.
- [ ] AI only explains analytics.
- [ ] AI receives structured JSON.
- [ ] AI output is validated.

---

# 11. NetSuite Review (Future)

- [ ] Only integrations/netsuite communicates with NetSuite.
- [ ] No raw API calls outside NetSuite client.
- [ ] Mapping layer exists.
- [ ] Internal IDs are preserved.
- [ ] Sync process is idempotent.

---

# 12. Testing

- [ ] Manual testing completed.
- [ ] Edge cases considered.
- [ ] Errors handled gracefully.

---

# 13. Documentation

- [ ] Documentation updated if implementation changed architecture.
- [ ] README updated if setup changed.
- [ ] Context documents remain accurate.

---

# 14. Performance

- [ ] No unnecessary database queries.
- [ ] No repeated calculations.
- [ ] No premature optimization.

---

# 15. Final Verification

Before finishing, verify:

- [ ] Project builds successfully.
- [ ] No broken imports.
- [ ] No syntax errors.
- [ ] No TODOs left unintentionally.
- [ ] No debug print statements.
- [ ] No temporary code.
- [ ] No placeholder credentials.
- [ ] Implementation stays within the approved scope.

---

# Required Final Report

Every implementation must end with:

## Implementation Status

### Completed

...

### Not Implemented

...

### Files Created

...

### Files Modified

...

### Packages Installed

...

### Manual Verification

...

### Assumptions

...

### Technical Debt

...

### Suggested Commit Message

...

### Self Review Summary

- Overall Quality:
- Architecture:
- Security:
- Maintainability:
- Scope Compliance:
- Confidence Level: