package cache

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "fmt"
    "log"
    "os"
    "path/filepath"
    "strings"
    "time"
)

// CacheConfig holds the configuration for the file cache.
type CacheConfig struct {
    // BaseDir is the root directory where caches are stored. 
    // If empty, it defaults to the OS temp dir + "/opt360_cache".
    BaseDir string
}

// FileCache handles file-based caching with TTL.
type FileCache struct {
    baseDir string
}

// NewFileCache initializes a new FileCache instance.
func NewFileCache(cfg CacheConfig) *FileCache {
    baseDir := cfg.BaseDir
    if baseDir == "" {
        baseDir = filepath.Join(os.TempDir(), "opt360_cache")
    }

    // Ensure the base directory exists
    if err := os.MkdirAll(baseDir, 0o755); err != nil {
        log.Printf("[FileCache] Warning: could not create base cache dir %s: %v", baseDir, err)
    }

    return &FileCache{baseDir: baseDir}
}

// GenerateKey creates a filesystem-safe, deterministic hash from multiple string parts.
// This ensures that "Lucknow", "UP", "Lucknow" always maps to the same file.
func GenerateKey(parts ...string) string {
    raw := strings.ToLower(strings.Join(parts, "|"))
    sum := sha256.Sum256([]byte(raw))
    return hex.EncodeToString(sum[:])
}

// Get attempts to read a cached value. 
// It returns the data, a boolean indicating if a fresh cache hit occurred, and an error.
func (fc *FileCache) Get(subDir, key string, ttl time.Duration, dest interface{}) (bool, error) {
    dir := filepath.Join(fc.baseDir, subDir)
    if err := os.MkdirAll(dir, 0o755); err != nil {
        return false, fmt.Errorf("failed to create cache subdir: %w", err)
    }

    filePath := filepath.Join(dir, key+".json")

    info, err := os.Stat(filePath)
    if err != nil {
        if os.IsNotExist(err) {
            return false, nil // Cache miss
        }
        return false, err
    }

    // Check if the cache is stale
    if time.Since(info.ModTime()) > ttl {
        // Best-effort eviction of stale file
        _ = os.Remove(filePath)
        return false, nil
    }

    // Read the cached file
    body, err := os.ReadFile(filePath)
    if err != nil {
        return false, err
    }

    // Unmarshal into the destination
    if err := json.Unmarshal(body, dest); err != nil {
        return false, err
    }

    return true, nil
}

// Set writes data to the cache as a JSON file atomically.
func (fc *FileCache) Set(subDir, key string, data interface{}) error {
    dir := filepath.Join(fc.baseDir, subDir)
    if err := os.MkdirAll(dir, 0o755); err != nil {
        return fmt.Errorf("failed to create cache subdir: %w", err)
    }

    filePath := filepath.Join(dir, key+".json")
    tmpPath := filePath + ".tmp"

    body, err := json.Marshal(data)
    if err != nil {
        return err
    }

    // Write to a temp file first
    if err := os.WriteFile(tmpPath, body, 0o644); err != nil {
        return err
    }

    // Atomically rename to the actual cache file (prevents partial reads)
    if err := os.Rename(tmpPath, filePath); err != nil {
        _ = os.Remove(tmpPath)
        return err
    }

    return nil
}