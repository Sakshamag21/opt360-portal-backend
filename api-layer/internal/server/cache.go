package server

import (
	"sort"
	"sync"
	"time"
)

type cacheEntry struct {
	data     []string
	expiry   time.Time
	accessed time.Time
	size     int
}

// sidCache is an in-process, TTL + size-bounded, per-key-locked cache for
// "all SIDs for operator+date" lookups. It ports the module-level
// _cache_store / _cache_locks / _global_lock globals from
// src/sid_details/all_sids.py. Being process-local, it is NOT shared across
// multiple worker processes or replicas and resets on every restart.
type sidCache struct {
	mu       sync.Mutex
	store    map[string]*cacheEntry
	locks    map[string]*sync.Mutex
	maxBytes int
}

func newSidCache(maxBytes int) *sidCache {
	return &sidCache{
		store:    make(map[string]*cacheEntry),
		locks:    make(map[string]*sync.Mutex),
		maxBytes: maxBytes,
	}
}

// fetchLock returns a per-key mutex (creating it on first use) so concurrent
// requests for the same cache key don't stampede the backing RocksDB call.
func (c *sidCache) fetchLock(key string) *sync.Mutex {
	c.mu.Lock()
	defer c.mu.Unlock()
	l, ok := c.locks[key]
	if !ok {
		l = &sync.Mutex{}
		c.locks[key] = l
	}
	return l
}

func (c *sidCache) get(key string) ([]string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	entry, ok := c.store[key]
	if !ok {
		return nil, false
	}
	if time.Now().After(entry.expiry) {
		delete(c.store, key)
		return nil, false
	}
	entry.accessed = time.Now()
	return entry.data, true
}

func (c *sidCache) set(key string, data []string, size int, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.store[key] = &cacheEntry{
		data:     data,
		expiry:   time.Now().Add(ttl),
		accessed: time.Now(),
		size:     size,
	}
	c.evictLocked()
}

// cleanup removes expired entries and enforces maxBytes via LRU eviction.
func (c *sidCache) cleanup() {
	c.mu.Lock()
	defer c.mu.Unlock()

	now := time.Now()
	for k, v := range c.store {
		if now.After(v.expiry) {
			delete(c.store, k)
			delete(c.locks, k)
		}
	}
	c.evictLocked()
}

// evictLocked assumes c.mu is already held.
func (c *sidCache) evictLocked() {
	total := 0
	for _, v := range c.store {
		total += v.size
	}
	if total <= c.maxBytes {
		return
	}

	type keyAccess struct {
		key      string
		accessed time.Time
	}
	entries := make([]keyAccess, 0, len(c.store))
	for k, v := range c.store {
		entries = append(entries, keyAccess{k, v.accessed})
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].accessed.Before(entries[j].accessed) })

	for _, e := range entries {
		if total <= c.maxBytes {
			break
		}
		total -= c.store[e.key].size
		delete(c.store, e.key)
		delete(c.locks, e.key)
	}
}

// stats returns the current item count and total cached byte size, used for
// diagnostic logging (mirrors _log_cache_state in the Python original).
func (c *sidCache) stats() (items int, totalBytes int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	items = len(c.store)
	for _, v := range c.store {
		totalBytes += v.size
	}
	return
}
