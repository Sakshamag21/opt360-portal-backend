package User

import (
	"log"
	"net/http"

	"opt360-portal-backend/middleware"
	"opt360-portal-backend/models"
	"opt360-portal-backend/session"

	"github.com/gin-gonic/gin"
)

// GetUserInfo returns the current user's information and regional office
func GetUserInfo(c *gin.Context) {
	u, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user := u.(*models.User)
	log.Printf("[GetUserInfo] Returning info for user=%s role=%s ro=%s", user.ADID, user.Role, user.RegionalOffice)
	c.JSON(http.StatusOK, user)
}

// UpdateRORequest represents the request body for updating regional office/group
type UpdateRORequest struct {
	Group string `json:"group" binding:"required"`
}

// UpdateRO updates the group/regional office for a user
func UpdateRO(c *gin.Context) {
	var req UpdateRORequest

	// Bind and validate request body
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}

	// Extract user_id from JWT token (stored in context by auth middleware)
	claims, exists := c.Get("token_claims")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Token claims not found in context"})
		return
	}

	// Type assert to get the claims
	tokenClaims, ok := claims.(*middleware.TokenClaims)
	if !ok {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse token claims"})
		return
	}

	userID := tokenClaims.Sub
	if userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User ID not found in token"})
		return
	}

	sessionManager := session.GetSessionManager()
	sessionManager.SetUserRegionalOffice(userID, req.Group)

	log.Printf("[UpdateRO] Session RO updated for user=%s to group=%s", userID, req.Group)
	c.JSON(http.StatusOK, gin.H{"message": "User regional office updated for session", "user_id": userID, "group": req.Group})
}

