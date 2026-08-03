package auth

import (
	"log"
	"sync"
	"time"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"
)

// userCacheTTL is how long a cached user lookup is considered fresh before a
// background refresh is triggered. It does NOT bound how quickly role/status
// changes propagate — mutations call InvalidateUserCache directly, which
// forces the very next lookup to block on a real DB read regardless of TTL.
// This just controls how often an otherwise-idle cache entry gets refreshed
// in the background.
const userCacheTTL = 5 * time.Minute

type cachedUser struct {
	user     *models.User
	cachedAt time.Time
}

// call represents one in-flight portal_users fetch for a given adID. Both
// the blocking (true cache-miss) and background (stale-refresh) paths go
// through fetchOnce, so concurrent lookups for the same adID — whether
// several requests racing a cold cache or a stale-triggered refresh
// overlapping an invalidation — collapse into a single DB query instead of
// each opening their own ~23s connection.
type call struct {
	wg   sync.WaitGroup
	user *models.User
	err  error
}

var (
	userCache sync.Map // adID -> *cachedUser
	inflight  sync.Map // adID -> *call
)

// fetchOnce runs db.GetUserByADID for adID, de-duplicating concurrent
// callers so only one actually hits the DB; the rest wait on its result.
func fetchOnce(adID string) (*models.User, error) {
	c := &call{}
	c.wg.Add(1)

	actual, loaded := inflight.LoadOrStore(adID, c)
	ac := actual.(*call)
	if loaded {
		// Someone else is already fetching this adID — wait for them instead
		// of issuing a second concurrent query.
		ac.wg.Wait()
		return ac.user, ac.err
	}

	ac.user, ac.err = db.GetUserByADID(adID)
	inflight.Delete(adID)
	ac.wg.Done()
	return ac.user, ac.err
}

// GetUserByADID retrieves user information with an in-memory cache, tuned so
// the auth middleware (called on every /api/* request) is never blocked on
// the slow portal_users DB except when it genuinely has to be:
//   - Fresh cache hit: returned instantly, no DB involved.
//   - Stale cache hit (TTL elapsed, but an entry exists): the stale value is
//     returned immediately and a de-duplicated background refresh is kicked
//     off to update the cache — the slow DB round-trip never sits in the
//     request path.
//   - True cache miss (nothing cached — first lookup for this adID, or right
//     after InvalidateUserCache from a profile/team mutation): blocks on a
//     real DB read, so login and profile/team actions always observe
//     genuinely fresh state rather than a stale or missing cache entry.
func GetUserByADID(adID string) (*models.User, bool) {
	if entry, ok := userCache.Load(adID); ok {
		cu := entry.(*cachedUser)
		if time.Since(cu.cachedAt) < userCacheTTL {
			return cu.user, true
		}

		// Stale: serve what we have now, refresh in the background. Errors
		// during refresh are logged and otherwise ignored — the stale entry
		// stays in place and gets retried on the next stale hit.
		go func() {
			user, err := fetchOnce(adID)
			if err != nil {
				log.Printf("[auth] background refresh failed for adID '%s': %v (continuing to serve stale cache)", adID, err)
				return
			}
			userCache.Store(adID, &cachedUser{user: user, cachedAt: time.Now()})
		}()
		return cu.user, true
	}

	// True miss — block for a real answer.
	user, err := fetchOnce(adID)
	if err != nil {
		log.Printf("Error getting user by ADID '%s': %v", adID, err)
		return nil, false
	}

	userCache.Store(adID, &cachedUser{user: user, cachedAt: time.Now()})
	return user, true
}

// InvalidateUserCache removes a single user's cached entry. Call this after
// any mutation that changes the user's DB state (status, role, group, email)
// so the next lookup is a true cache miss and blocks on a fresh DB read
// instead of serving a stale value or waiting for the TTL to expire.
func InvalidateUserCache(adID string) {
	userCache.Delete(adID)
}

// GetAllUsers retrieves all users from database
func GetAllUsers() ([]models.User, error) {
	return db.GetAllUsers()
}
