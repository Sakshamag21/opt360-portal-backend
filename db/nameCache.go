package db

import (
	"log"
	"sync"
	"time"

	"opt360-portal-backend/models"
)

// nameCacheRefreshInterval controls how often EA/Registrar name-code pairs
// are re-read from opt_master after the initial startup load, so newly
// added/renamed EAs and registrars show up without a restart.
const nameCacheRefreshInterval = 30 * time.Minute

var (
	eaCache  []models.NameCode
	regCache []models.NameCode
	nameMu   sync.RWMutex

	nameCacheOnce sync.Once
)

// InitNameCache loads EA and Registrar name-code pairs from opt_master once
// at startup, then keeps refreshing them on nameCacheRefreshInterval in the
// background for the life of the process. Like InitRiskBucketCache, this
// exists so handlers/OperatorTab/operatorFilters.go's dropdown data doesn't
// need a live query on every request — these lists change rarely (new EAs/
// registrars are not a common, fast-moving thing) but should still pick up
// changes without a redeploy.
func InitNameCache() {
	nameCacheOnce.Do(func() {
		refreshNameCache()
		go func() {
			ticker := time.NewTicker(nameCacheRefreshInterval)
			defer ticker.Stop()
			for range ticker.C {
				refreshNameCache()
			}
		}()
	})
}

func refreshNameCache() {
	database, err := GetDB()
	if err != nil {
		log.Printf("[NameCache] DB unavailable, keeping previous cache: %v", err)
		return
	}

	eas, err := fetchNameCodePairsFromDB(database, "ea", "ea_code")
	if err != nil {
		log.Printf("[NameCache] Failed to refresh EAs, keeping previous cache: %v", err)
	} else {
		nameMu.Lock()
		eaCache = eas
		nameMu.Unlock()
	}

	regs, err := fetchNameCodePairsFromDB(database, "reg", "reg_code")
	if err != nil {
		log.Printf("[NameCache] Failed to refresh registrars, keeping previous cache: %v", err)
	} else {
		nameMu.Lock()
		regCache = regs
		nameMu.Unlock()
	}

	log.Printf("[NameCache] Refreshed: %d EAs, %d registrars", len(eas), len(regs))
}

// fetchNameCodePairsFromDB is the same "SELECT DISTINCT name, code" query
// operatorFilters.go's fetchNameCodePairs runs on demand, extracted here so
// the cache's periodic refresh and any live/RO-scoped lookup share one
// implementation. nameCol/codeCol are always one of a small fixed set of
// literals passed by callers in this package (never user input).
func fetchNameCodePairsFromDB(database *LoggedDB, nameCol, codeCol string) ([]models.NameCode, error) {
	query := "SELECT DISTINCT " + nameCol + ", " + codeCol + " FROM operator360.opt_master" +
		" WHERE " + nameCol + " IS NOT NULL AND " + codeCol + " IS NOT NULL ORDER BY " + nameCol

	rows, err := database.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	pairs := make([]models.NameCode, 0)
	for rows.Next() {
		var nc models.NameCode
		if err := rows.Scan(&nc.Name, &nc.Code); err != nil {
			return nil, err
		}
		pairs = append(pairs, nc)
	}
	return pairs, rows.Err()
}

// GetCachedEAs returns the cached EA name-code pairs.
func GetCachedEAs() []models.NameCode {
	nameMu.RLock()
	defer nameMu.RUnlock()
	return eaCache
}

// GetCachedRegistrars returns the cached Registrar name-code pairs.
func GetCachedRegistrars() []models.NameCode {
	nameMu.RLock()
	defer nameMu.RUnlock()
	return regCache
}
