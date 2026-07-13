-- Adds the columns needed for the Profile + My Team feature (docs/RBAC_PLAN.md).
-- Run manually against the portal DB (strot_services.opt360_portal_users) — there is
-- no migration runner in this repo yet.

ALTER TABLE opt360_portal_users
  ADD COLUMN email      VARCHAR(255) NULL,
  ADD COLUMN status     ENUM('active','inactive') NOT NULL DEFAULT 'active',
  ADD COLUMN last_login DATETIME NULL,
  ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN created_by VARCHAR(64) NULL;

-- Existing rows: status defaults to 'active' automatically via the DEFAULT clause above.
-- email / last_login / created_by remain NULL for pre-existing users until they update
-- their email, next log in, or are edited by an admin/superadmin — application code
-- must treat these as optional (see models.User).
