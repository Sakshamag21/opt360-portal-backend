package auth

import (
	"log"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"
)

// GetUserByADID retrieves user information from database
func GetUserByADID(adID string) (*models.User, bool) {
	user, err := db.GetUserByADID(adID)
	if err != nil {
		log.Printf("Error getting user by ADID '%s': %v", adID, err)
		return nil, false
	}
	return user, true
}

// GetAllUsers retrieves all users from database
func GetAllUsers() ([]models.User, error) {
	return db.GetAllUsers()
}
