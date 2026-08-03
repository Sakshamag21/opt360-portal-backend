package LandingPage

import "opt360-portal-backend/cache"

// landingCache is a shared file-based cache for the LandingPage package.
// It is used to cache S3/DB responses on a per-RO basis to reduce latency
// and avoid redundant upstream calls.
var landingCache = cache.NewFileCache(cache.CacheConfig{})