package sync

import (
	"os"
	"path/filepath"
	"testing"

	"skillshare/internal/config"
)

// createTempSkill creates a skill directory with a SKILL.md containing the given name.
func createTempSkill(t *testing.T, dir, relPath, skillName string) DiscoveredSkill {
	t.Helper()
	skillDir := filepath.Join(dir, relPath)
	if err := os.MkdirAll(skillDir, 0755); err != nil {
		t.Fatalf("mkdir %s: %v", skillDir, err)
	}
	content := "---\nname: " + skillName + "\n---\n# " + skillName
	if err := os.WriteFile(filepath.Join(skillDir, "SKILL.md"), []byte(content), 0644); err != nil {
		t.Fatalf("write SKILL.md: %v", err)
	}
	return DiscoveredSkill{
		SourcePath: skillDir,
		RelPath:    relPath,
		FlatName:   relPath, // simplified for tests
	}
}

func TestCheckNameCollisionsForTargets_NoCollisions(t *testing.T) {
	dir := t.TempDir()
	skills := []DiscoveredSkill{
		createTempSkill(t, dir, "skill-a", "alpha"),
		createTempSkill(t, dir, "skill-b", "beta"),
	}

	targets := map[string]config.TargetConfig{
		"claude": {Path: "/tmp/claude", Mode: "merge"},
	}

	global, perTarget := CheckNameCollisionsForTargets(skills, targets)
	if len(global) != 0 {
		t.Errorf("expected no global collisions, got %d", len(global))
	}
	if len(perTarget) != 0 {
		t.Errorf("expected no per-target collisions, got %d", len(perTarget))
	}
}

func TestCheckNameCollisionsForTargets_GlobalCollisionIsolatedByFilter(t *testing.T) {
	dir := t.TempDir()
	// Two skills with the same SKILL.md name but different flat names
	skills := []DiscoveredSkill{
		createTempSkill(t, dir, "codex-plan", "planner"),
		createTempSkill(t, dir, "gemini-plan", "planner"),
	}

	targets := map[string]config.TargetConfig{
		"codex-target": {
			Path:    "/tmp/codex",
			Mode:    "merge",
			Include: []string{"codex-*"},
		},
		"gemini-target": {
			Path:    "/tmp/gemini",
			Mode:    "merge",
			Include: []string{"gemini-*"},
		},
	}

	global, perTarget := CheckNameCollisionsForTargets(skills, targets)
	if len(global) != 1 {
		t.Fatalf("expected 1 global collision, got %d", len(global))
	}
	if global[0].Name != "planner" {
		t.Errorf("expected collision name 'planner', got '%s'", global[0].Name)
	}
	if len(perTarget) != 0 {
		t.Errorf("expected no per-target collisions (filters isolate), got %d", len(perTarget))
	}
}

func TestCheckNameCollisionsForTargets_UnresolvedPerTargetCollision(t *testing.T) {
	dir := t.TempDir()
	skills := []DiscoveredSkill{
		createTempSkill(t, dir, "repo-a__plan", "planner"),
		createTempSkill(t, dir, "repo-b__plan", "planner"),
	}

	// No filters — collision passes through to per-target check?
	// Actually, no filters means the target is skipped in per-target loop.
	// So we need a target WITH filters that still includes both.
	targets := map[string]config.TargetConfig{
		"claude": {
			Path:    "/tmp/claude",
			Mode:    "merge",
			Include: []string{"repo-*"},
		},
	}

	global, perTarget := CheckNameCollisionsForTargets(skills, targets)
	if len(global) != 1 {
		t.Fatalf("expected 1 global collision, got %d", len(global))
	}
	if len(perTarget) != 1 {
		t.Fatalf("expected 1 per-target collision, got %d", len(perTarget))
	}
	if perTarget[0].TargetName != "claude" {
		t.Errorf("expected target 'claude', got '%s'", perTarget[0].TargetName)
	}
}

func TestCheckNameCollisionsForTargets_SymlinkModeSkipped(t *testing.T) {
	dir := t.TempDir()
	skills := []DiscoveredSkill{
		createTempSkill(t, dir, "codex-plan", "planner"),
		createTempSkill(t, dir, "gemini-plan", "planner"),
	}

	targets := map[string]config.TargetConfig{
		"symlink-target": {
			Path:    "/tmp/sym",
			Mode:    "symlink",
			Include: []string{"*-plan"},
		},
	}

	global, perTarget := CheckNameCollisionsForTargets(skills, targets)
	if len(global) != 1 {
		t.Fatalf("expected 1 global collision, got %d", len(global))
	}
	// symlink mode targets should be skipped
	if len(perTarget) != 0 {
		t.Errorf("expected no per-target collisions for symlink mode, got %d", len(perTarget))
	}
}

func TestCheckNameCollisionsForTargets_NoFilterTargetSkipped(t *testing.T) {
	dir := t.TempDir()
	skills := []DiscoveredSkill{
		createTempSkill(t, dir, "skill-a", "planner"),
		createTempSkill(t, dir, "skill-b", "planner"),
	}

	// Target with no filters — skipped in per-target loop (same as global)
	targets := map[string]config.TargetConfig{
		"claude": {Path: "/tmp/claude", Mode: "merge"},
	}

	global, perTarget := CheckNameCollisionsForTargets(skills, targets)
	if len(global) != 1 {
		t.Fatalf("expected 1 global collision, got %d", len(global))
	}
	if len(perTarget) != 0 {
		t.Errorf("expected no per-target collisions (no filters = skip), got %d", len(perTarget))
	}
}
