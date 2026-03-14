package backup

import (
	"os"
	"path/filepath"
	"time"
)

// CleanupConfig holds backup cleanup configuration
type CleanupConfig struct {
	MaxAge    time.Duration // Maximum age of backups to keep (0 = no limit)
	MaxCount  int           // Maximum number of backups to keep (0 = no limit)
	MaxSizeMB int64         // Maximum total size in MB (0 = no limit)
}

// DefaultCleanupConfig returns sensible defaults for cleanup
func DefaultCleanupConfig() CleanupConfig {
	return CleanupConfig{
		MaxAge:    30 * 24 * time.Hour, // 30 days
		MaxCount:  10,                  // Keep last 10 backups
		MaxSizeMB: 500,                 // 500 MB max
	}
}

// Cleanup removes old backups based on the configuration.
// Returns the number of backups removed and any error encountered.
func Cleanup(cfg CleanupConfig) (int, error) {
	backups, err := List()
	if err != nil {
		return 0, err
	}

	if len(backups) == 0 {
		return 0, nil
	}

	removed := 0
	now := time.Now()
	var totalSize int64

	// Backups are sorted by date (newest first)
	for i, backup := range backups {
		shouldRemove := false

		// Check age (skip if MaxAge is 0)
		if cfg.MaxAge > 0 && now.Sub(backup.Date) > cfg.MaxAge {
			shouldRemove = true
		}

		// Check count - keep most recent N backups (skip if MaxCount is 0)
		if cfg.MaxCount > 0 && i >= cfg.MaxCount {
			shouldRemove = true
		}

		// Check size - remove if total exceeds limit (skip if MaxSizeMB is 0)
		size := dirSize(backup.Path)
		totalSize += size
		if cfg.MaxSizeMB > 0 && totalSize > cfg.MaxSizeMB*1024*1024 {
			shouldRemove = true
		}

		if shouldRemove {
			if err := os.RemoveAll(backup.Path); err != nil {
				// Log but continue with other backups
				continue
			}
			removed++
		}
	}

	// Clean up empty timestamp directories
	cleanEmptyDirs(BackupDir())

	return removed, nil
}

// CleanupByAge removes backups older than the specified duration.
// Returns the number of backups removed.
func CleanupByAge(maxAge time.Duration) (int, error) {
	return Cleanup(CleanupConfig{MaxAge: maxAge})
}

// CleanupByCount keeps only the N most recent backups.
// Returns the number of backups removed.
func CleanupByCount(maxCount int) (int, error) {
	return Cleanup(CleanupConfig{MaxCount: maxCount})
}

// dirSize calculates the total size of a directory
func dirSize(path string) int64 {
	var size int64
	filepath.Walk(path, func(_ string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if !info.IsDir() {
			size += info.Size()
		}
		return nil
	})
	return size
}

// cleanEmptyDirs removes empty directories in the backup directory
func cleanEmptyDirs(path string) {
	if path == "" {
		return
	}

	entries, err := os.ReadDir(path)
	if err != nil {
		return
	}

	for _, entry := range entries {
		if entry.IsDir() {
			subPath := filepath.Join(path, entry.Name())
			subEntries, _ := os.ReadDir(subPath)
			if len(subEntries) == 0 {
				os.Remove(subPath)
			}
		}
	}
}

// Size returns the total size of a backup directory in bytes
func Size(path string) int64 {
	return dirSize(path)
}

// TotalSize returns the total size of all backups in bytes
func TotalSize() (int64, error) {
	backups, err := List()
	if err != nil {
		return 0, err
	}

	var total int64
	for _, b := range backups {
		total += dirSize(b.Path)
	}
	return total, nil
}
