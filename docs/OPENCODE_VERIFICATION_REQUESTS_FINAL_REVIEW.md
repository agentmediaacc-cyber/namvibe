# Verification Requests — Final Review

**Commit:** `3273bb3`  
**Date:** 2026-06-28  
**Reviewer:** Cline (automated audit)

---

## 1. Route Registration in `app.py`

| Blueprint | Imported | Registered | Line |
|-----------|----------|------------|------|
| `verification_admin_bp` | `from api_routes.verification_admin_routes import verification_admin_bp` (line 82) | `app.register_blueprint(verification_admin_bp)` (line 551) | ✓ |
| `verification_bp` | `from api_routes.verification_routes import verification_bp` (line 54) | `app.register_blueprint(verification_bp)` (line 518) | ✓ |
| `profile_extra_bp` | `from api_routes.social_graph_routes import ... profile_extra_bp` (line 81) | `app.register_blueprint(profile_extra_bp)` (line 550) | ✓ |

**Verdict:** All verification-related blueprints are registered. PASS.

---

## 2. Admin Route Protection

All routes in `api_routes/verification_admin_routes.py` are decorated with `@require_admin`:

- `dashboard()` — `@require_admin` ✓
- `api_pending()` — `@require_admin` ✓
- `api_all()` — `@require_admin` ✓
- `api_detail(request_id)` — `@require_admin` ✓
- `api_approve()` — `@require_admin` ✓
- `api_reject()` — `@require_admin` ✓
- `api_request_info()` — `@require_admin` ✓

`require_admin` (from `services/admin_auth_service.py`) checks `session.get("admin_id")` and verifies the admin is active. Redirects to `/admin/login` on failure.

**Verdict:** All admin routes are properly protected. PASS.

---

## 3. User Verification Route Protection

All user-facing verification routes in `api_routes/social_graph_routes.py` (`profile_extra_bp`) use `@login_required`:

- `view_verification()` — `@login_required` ✓
- `api_submit_verification()` — `@login_required` ✓

The legacy `api_routes/verification_routes.py` also uses `@login_required` on all routes.

**Verdict:** All user verification routes require authentication. PASS.

---

## 4. SQL Schema vs Service Code Alignment

### Table: `chain_verification_documents`

| Column | SQL (058_phase158d_tables.sql) | Service (`verification_request_service.py`) | Match |
|--------|-------------------------------|---------------------------------------------|-------|
| `id` | UUID PRIMARY KEY | Used in INSERT, SELECT, UPDATE | ✓ |
| `profile_id` | UUID FK → chain_profiles | Used in INSERT, SELECT, UPDATE | ✓ |
| `id_front_url` | TEXT | Used in INSERT | ✓ |
| `id_back_url` | TEXT | Used in INSERT | ✓ |
| `address_proof_url` | TEXT | Used in INSERT | ✓ |
| `address_proof_type` | TEXT DEFAULT 'water_bill' | Used in INSERT | ✓ |
| `selfie_video_url` | TEXT | Used in INSERT | ✓ |
| `whatsapp_phone` | TEXT | Used in INSERT | ✓ |
| `whatsapp_code` | TEXT | Used in INSERT | ✓ |
| `status` | TEXT CHECK (pending,approved,rejected,needs_more_info) | Used in INSERT, SELECT, UPDATE | ✓ |
| `admin_notes` | TEXT | Read in `get_verification_status` | ✓ |
| `reviewed_by` | UUID | Written in approve/reject/request-info | ✓ |
| `reviewed_at` | TIMESTAMPTZ | Read in `get_verification_status` | ✓ |
| `submitted_at` | TIMESTAMPTZ DEFAULT now() | Read in `get_verification_status` | ✓ |
| `updated_at` | TIMESTAMPTZ DEFAULT now() | Not used in service (acceptable) | ⚠️ |

### Profile columns used by `approve_verification`

| Column | SQL (058_phase158d_tables.sql) | Service | Match |
|--------|-------------------------------|---------|-------|
| `is_verified` | ALTER TABLE chain_profiles ADD COLUMN (line 94 in chain_neon_core_schema.sql) | `UPDATE chain_profiles SET is_verified = TRUE` | ✓ |
| `verified` | ALTER TABLE chain_profiles ADD COLUMN (line 95 in chain_neon_core_schema.sql) | `UPDATE chain_profiles SET verified = TRUE` | ✓ |
| `verification_date` | ALTER TABLE chain_profiles ADD COLUMN (line 97 in 058_phase158d_tables.sql) | `UPDATE chain_profiles SET verification_date = now()` | ✓ |

**Verdict:** Schema matches service code. PASS.

---

## 5. Upload Storage Helpers

### Upload flow

1. Template submits multipart form to `/profile/api/verification/submit`
2. `api_submit_verification()` in `social_graph_routes.py` checks for files:
   - `id_front` → `upload_verification_file(profile_id, file, "id_front")`
   - `id_back` → `upload_verification_file(profile_id, file, "id_back")`
   - `address_proof` → `upload_verification_file(profile_id, file, "address_proof")`
   - `selfie_video` → `upload_verification_file(profile_id, file, "selfie")`
3. `upload_verification_file()` calls `upload_file_to_bucket(file, 'chain-verification', profile_id, upload_type, public=False)`
4. `upload_file_to_bucket()` validates file type and size, then uploads to Supabase or local fallback

### Bug Fixed: PDF uploads blocked for address_proof

The `upload_file_to_bucket()` function's category mapping only recognized `'verification_doc'` and `'payment_proof'` as `'documents'` (which allows PDF). The actual upload types passed (`'id_front'`, `'id_back'`, `'address_proof'`, `'selfie'`) fell through to the default `'images'` category, which does NOT allow PDF. Since the template accepts `application/pdf` for address_proof, this would cause PDF uploads to fail.

**Fix:** Added `'id_front'`, `'id_back'`, `'address_proof'`, `'selfie'` to the `'documents'` category in `upload_file_to_bucket()`.

### Verification docs are private

`upload_verification_file()` passes `public=False`, which is correct for sensitive identity documents.

**Verdict:** Uploads use existing helpers correctly. One bug fixed. PASS (after fix).

---

## 6. Template Form Fields vs Backend

| Template field (`name=`) | Backend reads | Match |
|--------------------------|---------------|-------|
| `id_front` (file) | `files.get("id_front")` | ✓ |
| `id_back` (file) | `files.get("id_back")` | ✓ |
| `address_proof` (file) | `files.get("address_proof")` | ✓ |
| `address_proof_type` (select) | `data.get("address_proof_type")` | ✓ |
| `selfie_video` (file) | `files.get("selfie_video")` | ✓ |
| `whatsapp_phone` (tel) | `data.get("whatsapp_phone")` | ✓ |
| `whatsapp_code` (text) | `data.get("whatsapp_code")` | ✓ |

Form action: `/profile/api/verification/submit` (POST)  
Route: `@profile_extra_bp.route("/api/verification/submit", methods=["POST"])` with `url_prefix="/profile"` → resolves to `/profile/api/verification/submit` ✓

**Verdict:** Template fields match backend expectations. PASS.

---

## 7. API Response Shapes

### Admin approve/reject/request-info endpoints

All return `{"ok": True}` on success or `{"ok": False, "error": "..."}` on failure.

| Endpoint | Success shape | Error shape | HTTP error codes |
|----------|--------------|-------------|------------------|
| `POST /admin/verifications/api/approve` | `{"ok": True}` | `{"ok": False, "error": "..."}` | 400 for missing request_id |
| `POST /admin/verifications/api/reject` | `{"ok": True}` | `{"ok": False, "error": "..."}` | 400 for missing request_id |
| `POST /admin/verifications/api/request-info` | `{"ok": True}` | `{"ok": False, "error": "..."}` | 400 for missing request_id |
| `GET /admin/verifications/api/pending` | `{"ok": True, "pending": [...]}` | — | — |
| `GET /admin/verifications/api/all` | `{"ok": True, "verifications": [...]}` | — | — |
| `GET /admin/verifications/api/detail/<id>` | `{"ok": True, "verification": {...}}` | `{"ok": False, "error": "Not found."}` | 404 |

### User submit endpoint

| Endpoint | Success shape | Error shape |
|----------|--------------|-------------|
| `POST /profile/api/verification/submit` | `{"ok": True, "request_id": "..."}` | `{"ok": False, "error": "..."}` |

### User status endpoint

| Endpoint | Success shape |
|----------|--------------|
| `GET /profile/api/verification/status` (via `verification_routes.py`) | `{"status": "...", "request_id": "...", ...}` |

**Verdict:** Response shapes are consistent. PASS.

---

## 8. Compilation & Route Verification Results

| Check | Result |
|-------|--------|
| `python3 -m py_compile app.py` | PASS (exit 0) |
| `python3 -m compileall api_routes services templates` | PASS (exit 0) |
| `python3 scripts/verify_production_routes.py` | PASS |
| `python3 scripts/benchmark_production_routes.py` | PASS |

---

## 9. Runtime Bugs Fixed

### Bug #1: PDF uploads rejected for verification documents

**File:** `services/storage_service.py`  
**Function:** `upload_file_to_bucket()`  
**Problem:** The category mapping only recognized `'verification_doc'` and `'payment_proof'` as `'documents'` (which allows PDF). The actual upload types passed from `api_submit_verification()` are `'id_front'`, `'id_back'`, `'address_proof'`, `'selfie'`. These fell through to the default `'images'` category, which does NOT include `pdf`. Since the template accepts `application/pdf` for address_proof, any PDF upload would fail with "File type not allowed for images".  
**Fix:** Added `'id_front'`, `'id_back'`, `'address_proof'`, `'selfie'` to the `'documents'` category check.

---

## 10. Files Safe to Commit

All files listed below are safe to commit. No secrets, migrations, table renames, or fake data are included.

- `api_routes/verification_admin_routes.py` — no changes needed
- `services/verification_request_service.py` — no changes needed
- `templates/profile/verification_request.html` — no changes needed
- `sql/058_phase158d_tables.sql` — no changes needed
- `services/storage_service.py` — **one-line fix** (added verification upload types to documents category)
- `docs/OPENCODE_VERIFICATION_REQUESTS_FINAL_REVIEW.md` — this file

---

## 11. Remaining Blockers

| Blocker | Severity | Notes |
|---------|----------|-------|
| `chain-verification` bucket must exist in Supabase | **HIGH** | If the bucket doesn't exist, uploads fall back to local storage. Local storage URLs won't be accessible in production. |
| `chain_verification_documents` table must exist | **HIGH** | The SQL migration `058_phase158d_tables.sql` must be applied before verification requests work. |
| WhatsApp verification is placeholder | **LOW** | The `whatsapp_code` field is collected but no actual WhatsApp API integration sends codes. This is a UX gap, not a runtime bug. |
| No admin JS for approve/reject/request-info | **LOW** | The admin template `templates/admin/verifications.html` exists but was not reviewed for JS integration. The API shapes are correct. |

---

## 12. Suggested Commit Message

```
fix(verification): add verification upload types to documents category

- Fix PDF upload rejection for address_proof by adding 'id_front',
  'id_back', 'address_proof', 'selfie' to the 'documents' category
  in upload_file_to_bucket()
- Verify all admin routes are registered and protected with @require_admin
- Verify user routes use @login_required
- Verify SQL schema matches service code exactly
- Verify template form fields match backend expectations
- Verify API response shapes are consistent
- All compilation and route verification tests pass
```

---

## Summary

**7 of 7 verification checks pass.**  
**1 runtime bug fixed** (PDF uploads for verification documents).  
**0 breaking changes.**  
**Safe to commit** the listed files.