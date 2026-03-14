//go:build !windows

package sync

import (
	"os"
)

// createLink creates a symlink on Unix systems
func createLink(targetPath, sourcePath string) error {
	return os.Symlink(sourcePath, targetPath)
}

// isJunctionOrSymlink checks if path is a symlink
func isJunctionOrSymlink(path string) bool {
	info, err := os.Lstat(path)
	if err != nil {
		return false
	}
	return info.Mode()&os.ModeSymlink != 0
}
