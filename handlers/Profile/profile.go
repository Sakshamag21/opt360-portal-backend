package Profile

import (
	"log"
	"net/http"
	"net/mail"
	"strings"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// GetProfile handles POST /api/profile — returns the caller's own info.
// Side effect: stamps last_login to now (see db.UpdateLastLogin doc comment for why
// this is done here rather than on every authenticated request).
func GetProfile(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	if err := db.UpdateLastLogin(user.ADID); err != nil {
		// Non-fatal: don't fail the profile fetch just because the bookkeeping write failed.
		log.Printf("[GetProfile] Failed to update last_login for user=%s: %v", user.ADID, err)
	}

	c.JSON(http.StatusOK, user)
}

// UpdateEmail handles POST /api/profile/update_email — lets any authenticated
// user (any role) update their own email address. Self-service only; there is
// no ad_id in the body, it always targets the caller.
func UpdateEmail(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	var req models.UpdateEmailRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}

	email := strings.TrimSpace(req.Email)
	if _, err := mail.ParseAddress(email); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "A valid email address is required"})
		return
	}

	if err := db.UpdateUserEmail(user.ADID, email); err != nil {
		log.Printf("[UpdateEmail] Failed to update email for user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update email", "details": err.Error()})
		return
	}

	log.Printf("[UpdateEmail] user=%s updated their email", user.ADID)
	c.JSON(http.StatusOK, gin.H{"message": "Email updated successfully", "email": email})
}
