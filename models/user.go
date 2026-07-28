package models

import "time"

// User represents a user in the system
type User struct {
	ADID           string     `json:"ad_id" db:"user_id"`
	Name           string     `json:"name" db:"user_name"`
	RegionalOffice string     `json:"regional_office" db:"group"`
	Role           string     `json:"role" db:"role"`
	Email          *string    `json:"email,omitempty" db:"email"`
	Status         string     `json:"status" db:"status"`
	LastLogin      *time.Time `json:"last_login,omitempty" db:"last_login"`
	CreatedAt      *time.Time `json:"created_at,omitempty" db:"created_at"`
	CreatedBy      *string    `json:"created_by,omitempty" db:"created_by"`
}

// UsersConfig holds the complete users configuration (deprecated - for backward compatibility)
type UsersConfig struct {
	Users []User `json:"users"`
}

// ValidRoles are the only accepted values for User.Role.
var ValidRoles = map[string]bool{
	"user":       true,
	"admin":      true,
	"superadmin": true,
}

// ValidGroups are the only accepted values for User.RegionalOffice ("group").
var ValidGroups = map[string]bool{
	"Bangalore":    true,
	"Mumbai":       true,
	"Delhi":        true,
	"Lucknow":      true,
	"Hyderabad":    true,
	"Ranchi":       true,
	"Guwahati":     true,
	"Chandigarh":   true,
	"TechCentre":   true,
	"HeadQuarters": true,
}

// ValidStatuses are the only accepted values for User.Status.
var ValidStatuses = map[string]bool{
	"active":   true,
	"inactive": true,
}

// GlobalGroups are the groups that aren't a real Regional Office — users in
// these groups see data across all ROs by default (no RO filter applied),
// and may optionally select a specific RO to scope down to, unlike normal
// RO users who are always scoped to their own RO by default. Neither
// "TechCentre" nor "HeadQuarters" is a real value of opt_master.ro, so
// defaulting these users' own group onto an RO-scoped query the way a normal
// user's group would be is always wrong — it would silently match nothing.
var GlobalGroups = map[string]bool{
	"TechCentre":   true,
	"HeadQuarters": true,
}

// IsGlobalUser reports whether a user's group is a global (non-RO) group.
func IsGlobalUser(group string) bool {
	return GlobalGroups[group]
}

// ResolveRO returns the RO a request should be scoped by: an explicit
// override if the caller gave one, else the user's own RO for a normal
// user, or "" (global — no RO filter, all ROs) for a TechCentre/HeadQuarters
// user with no override. Every RO-scoped handler should resolve its filter
// through this instead of defaulting straight to user.RegionalOffice.
func ResolveRO(explicitRO string, user *User) string {
	if explicitRO != "" {
		return explicitRO
	}
	if IsGlobalUser(user.RegionalOffice) {
		return ""
	}
	return user.RegionalOffice
}

// UpdateEmailRequest is the body for POST /api/profile/update_email.
type UpdateEmailRequest struct {
	Email string `json:"email" binding:"required"`
}

// TeamRequest is the body for POST /api/team.
// Group is optional; only superadmin may set it to something other than their own group.
type TeamRequest struct {
	Group string `json:"group"`
}

// TeamResponse is the response for POST /api/team.
type TeamResponse struct {
	Data  []User `json:"data"`
	Group string `json:"group"`
}

// OnboardUserRequest is the body for POST /api/team/onboard.
// Role/Group are only honored for superadmin callers — admins always onboard into
// their own group with role "user" regardless of what's sent here.
type OnboardUserRequest struct {
	ADID  string `json:"ad_id" binding:"required"`
	Name  string `json:"name" binding:"required"`
	Email string `json:"email" binding:"required"`
	Role  string `json:"role"`
	Group string `json:"group"`
}

// UpdateUserRequest is the body for POST /api/team/update. Any subset of
// Status/Role/Group may be present; each is permission-checked independently
// (see handlers/Team/team.go).
type UpdateUserRequest struct {
	ADID   string  `json:"ad_id" binding:"required"`
	Status *string `json:"status"`
	Role   *string `json:"role"`
	Group  *string `json:"group"`
}
