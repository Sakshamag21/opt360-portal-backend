package session

import (
	"sync"
	"log"
)

// UserSession represents a user's session data
type UserSession struct {
	UserID          string
	RegionalOffice  string
}

// SessionManager manages user sessions in memory
type SessionManager struct {
	sessions sync.Map // map[string]*UserSession (userID -> session)
}

var (
	manager *SessionManager
	once    sync.Once
)

// GetSessionManager returns the singleton session manager instance
func GetSessionManager() *SessionManager {
	once.Do(func() {
		manager = &SessionManager{}
		log.Println("Session manager initialized")
	})
	return manager
}

// SetUserRegionalOffice stores the user's selected regional office in session
func (sm *SessionManager) SetUserRegionalOffice(userID, regionalOffice string) {
	session := &UserSession{
		UserID:         userID,
		RegionalOffice: regionalOffice,
	}
	sm.sessions.Store(userID, session)
	log.Printf("Session updated for user %s: regional office set to %s", userID, regionalOffice)
}

// GetUserRegionalOffice retrieves the user's session-stored regional office
func (sm *SessionManager) GetUserRegionalOffice(userID string) (string, bool) {
	if value, exists := sm.sessions.Load(userID); exists {
		if session, ok := value.(*UserSession); ok {
			return session.RegionalOffice, true
		}
	}
	return "", false
}

// ClearUserSession removes the user's session data
func (sm *SessionManager) ClearUserSession(userID string) {
	sm.sessions.Delete(userID)
	log.Printf("Session cleared for user %s", userID)
}

// HasUserSession checks if a user has an active session
func (sm *SessionManager) HasUserSession(userID string) bool {
	_, exists := sm.sessions.Load(userID)
	return exists
}