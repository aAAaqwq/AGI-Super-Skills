//go:build windows

package sync

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// createLink creates a directory junction on Windows (no admin required).
// Falls back to symlink if junction fails.
func createLink(targetPath, sourcePath string) error {
	// Ensure absolute paths for junction
	absSource, err := filepath.Abs(sourcePath)
	if err != nil {
		return fmt.Errorf("failed to resolve source path: %w", err)
	}
	absTarget, err := filepath.Abs(targetPath)
	if err != nil {
		return fmt.Errorf("failed to resolve target path: %w", err)
	}

	// Pre-flight checks with clear error messages
	if _, err := os.Stat(absSource); os.IsNotExist(err) {
		return fmt.Errorf("source directory does not exist: %s", absSource)
	}

	if info, err := os.Lstat(absTarget); err == nil {
		if info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("target already exists as a junction/symlink: %s", absTarget)
		}
		return fmt.Errorf("target already exists: %s", absTarget)
	}

	// Try junction first (no admin required)
	var stderr bytes.Buffer
	cmd := exec.Command("cmd", "/c", "mklink", "/J", absTarget, absSource)
	cmd.Stderr = &stderr
	if err := cmd.Run(); err == nil {
		return nil
	}

	junctionErr := strings.TrimSpace(stderr.String())

	// Fallback to symlink (requires admin/developer mode)
	if symlinkErr := os.Symlink(absSource, absTarget); symlinkErr == nil {
		return nil
	}

	// Both methods failed - provide helpful error message
	errMsg := "failed to create link"
	if junctionErr != "" {
		errMsg = fmt.Sprintf("%s\n  junction error: %s", errMsg, junctionErr)
	} else {
		errMsg = fmt.Sprintf("%s\n  junction: mklink /J command failed", errMsg)
	}
	errMsg = fmt.Sprintf("%s\n  symlink: requires Administrator or Developer Mode", errMsg)
	errMsg = fmt.Sprintf("%s\n  target: %s\n  source: %s", errMsg, absTarget, absSource)

	return errors.New(errMsg)
}

// isJunctionOrSymlink checks if path is a junction or symlink
func isJunctionOrSymlink(path string) bool {
	info, err := os.Lstat(path)
	if err != nil {
		return false
	}
	// Both junctions and symlinks have ModeSymlink on Windows
	return info.Mode()&os.ModeSymlink != 0
}
