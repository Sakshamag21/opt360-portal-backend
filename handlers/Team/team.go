package Team

import (
	"errors"
	"log"
	"net/http"
	"strings"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

func currentUser(c *gin.Context) (*models.User, bool) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return nil, false
	}
	return userInterface.(*models.User), true
}

func isSuperadmin(u *models.User) bool { return strings.EqualFold(u.Role, "superadmin") }
func isAdmin(u *models.User) bool      { return strings.EqualFold(u.Role, "admin") }

// GetTeam handles POST /api/team — lists users in a group ("My Team").
//
// Body: {"group": "<optional>"}. Defaults to the caller's own group. Only a
// superadmin may request a group other than their own; anyone else asking for
// a different group gets 403 (see docs/RBAC_PLAN.md permission matrix).
func GetTeam(c *gin.Context) {
	user, ok := currentUser(c)
	if !ok {
		return
	}

	var req models.TeamRequest
	if err := c.ShouldBindJSON(&req); err != nil && err.Error() != "EOF" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}

	group := strings.TrimSpace(req.Group)
	if group == "" {
		group = user.RegionalOffice
	} else if group != user.RegionalOffice && !isSuperadmin(user) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Only a superadmin may view another group's team"})
		return
	}

	if !models.ValidGroups[group] {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Unknown group", "accepted_values": groupList()})
		return
	}

	members, err := db.GetUsersByGroup(group)
	if err != nil {
		log.Printf("[GetTeam] Failed to fetch group=%s: %v", group, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch team", "details": err.Error()})
		return
	}

	c.JSON(http.StatusOK, models.TeamResponse{Data: members, Group: group})
}

// OnboardUser handles POST /api/team/onboard.
//
// Admins may onboard a user into their OWN group only, always with role "user"
// (any role/group sent in the body is ignored for admins — the server decides).
// Superadmins may onboard into any group with any role, and must supply both.
func OnboardUser(c *gin.Context) {
	user, ok := currentUser(c)
	if !ok {
		return
	}

	if !isAdmin(user) && !isSuperadmin(user) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Only admin or superadmin may onboard users"})
		return
	}

	var req models.OnboardUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}

	adID := strings.TrimSpace(req.ADID)
	name := strings.TrimSpace(req.Name)
	email := strings.TrimSpace(req.Email)
	if adID == "" || name == "" || email == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "ad_id, name and email are required"})
		return
	}

	newUser := models.User{
		ADID:   adID,
		Name:   name,
		Email:  &email,
		Status: "active",
	}
	createdBy := user.ADID
	newUser.CreatedBy = &createdBy

	if isSuperadmin(user) {
		role := strings.TrimSpace(req.Role)
		group := strings.TrimSpace(req.Group)
		if !models.ValidRoles[role] {
			c.JSON(http.StatusBadRequest, gin.H{"error": "role is required and must be one of the valid roles", "accepted_values": roleList()})
			return
		}
		if !models.ValidGroups[group] {
			c.JSON(http.StatusBadRequest, gin.H{"error": "group is required and must be one of the valid groups", "accepted_values": groupList()})
			return
		}
		newUser.Role = role
		newUser.RegionalOffice = group
	} else {
		// Admin: role and group are always forced server-side, regardless of what was sent.
		newUser.Role = "user"
		newUser.RegionalOffice = user.RegionalOffice
	}

	if err := db.CreateUser(newUser); err != nil {
		if errors.Is(err, db.ErrDuplicateUser) {
			c.JSON(http.StatusConflict, gin.H{"error": "A user with this ad_id already exists"})
			return
		}
		log.Printf("[OnboardUser] Failed to create user=%s: %v", adID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to onboard user", "details": err.Error()})
		return
	}

	log.Printf("[OnboardUser] user=%s onboarded new_user=%s role=%s group=%s", user.ADID, adID, newUser.Role, newUser.RegionalOffice)
	c.JSON(http.StatusCreated, newUser)
}

// UpdateUser handles POST /api/team/update — a single combined endpoint for the
// three "edit another user" mutations, each permission-checked independently:
//
//	status  – admin (own group only, target must already be in admin's group) or superadmin (any group)
//	role    – superadmin only
//	group   – superadmin only
//
// Sending a field the caller isn't permitted to change is a 403, not a silent no-op.
func UpdateUser(c *gin.Context) {
	user, ok := currentUser(c)
	if !ok {
		return
	}

	if !isAdmin(user) && !isSuperadmin(user) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Only admin or superadmin may update users"})
		return
	}

	var req models.UpdateUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}

	targetADID := strings.TrimSpace(req.ADID)
	if targetADID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "ad_id is required"})
		return
	}
	if req.Status == nil && req.Role == nil && req.Group == nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "At least one of status, role, group must be provided"})
		return
	}

	target, err := db.GetUserByADID(targetADID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "User not found", "ad_id": targetADID})
		return
	}

	// role / group: superadmin only.
	if req.Role != nil || req.Group != nil {
		if !isSuperadmin(user) {
			c.JSON(http.StatusForbidden, gin.H{"error": "Only a superadmin may change role or group"})
			return
		}
	}

	// status: admin (own group, target already in that group) or superadmin (any group).
	if req.Status != nil {
		if isAdmin(user) && target.RegionalOffice != user.RegionalOffice {
			c.JSON(http.StatusForbidden, gin.H{"error": "Admins may only change status for users in their own group"})
			return
		}
	}

	if req.Status != nil {
		status := strings.TrimSpace(*req.Status)
		if !models.ValidStatuses[status] {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid status", "accepted_values": []string{"active", "inactive"}})
			return
		}
		if err := db.UpdateUserStatus(targetADID, status); err != nil {
			log.Printf("[UpdateUser] Failed to update status for %s: %v", targetADID, err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update status", "details": err.Error()})
			return
		}
	}

	if req.Role != nil {
		role := strings.TrimSpace(*req.Role)
		if !models.ValidRoles[role] {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid role", "accepted_values": roleList()})
			return
		}
		if err := db.UpdateUserRole(targetADID, role); err != nil {
			log.Printf("[UpdateUser] Failed to update role for %s: %v", targetADID, err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update role", "details": err.Error()})
			return
		}
	}

	if req.Group != nil {
		group := strings.TrimSpace(*req.Group)
		if !models.ValidGroups[group] {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid group", "accepted_values": groupList()})
			return
		}
		if err := db.UpdateUserGroup(targetADID, group); err != nil {
			log.Printf("[UpdateUser] Failed to update group for %s: %v", targetADID, err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update group", "details": err.Error()})
			return
		}
	}

	updated, err := db.GetUserByADID(targetADID)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"message": "User updated"})
		return
	}

	log.Printf("[UpdateUser] user=%s updated target=%s", user.ADID, targetADID)
	c.JSON(http.StatusOK, updated)
}

func roleList() []string {
	roles := make([]string, 0, len(models.ValidRoles))
	for r := range models.ValidRoles {
		roles = append(roles, r)
	}
	return roles
}

func groupList() []string {
	groups := make([]string, 0, len(models.ValidGroups))
	for g := range models.ValidGroups {
		groups = append(groups, g)
	}
	return groups
}
