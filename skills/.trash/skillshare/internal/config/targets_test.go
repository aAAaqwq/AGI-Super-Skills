package config

import (
	"testing"
)

func TestGroupedProjectTargets_UniversalGrouped(t *testing.T) {
	grouped := GroupedProjectTargets()

	// Find the universal group entry
	var universalGroup *GroupedProjectTarget
	for i, g := range grouped {
		if g.Name == "universal" {
			universalGroup = &grouped[i]
			break
		}
	}

	if universalGroup == nil {
		t.Fatal("expected 'universal' group in GroupedProjectTargets result")
	}

	if universalGroup.Path != ".agents/skills" {
		t.Errorf("universal group path = %q, want %q", universalGroup.Path, ".agents/skills")
	}

	if len(universalGroup.Members) == 0 {
		t.Fatal("universal group should have members")
	}

	// Verify known members are present
	memberSet := make(map[string]bool)
	for _, m := range universalGroup.Members {
		memberSet[m] = true
	}

	expectedMembers := []string{"amp", "codex", "kimi", "replit"}
	for _, name := range expectedMembers {
		if !memberSet[name] {
			t.Errorf("expected %q in universal group members, got %v", name, universalGroup.Members)
		}
	}

	// Canonical name should NOT be in members
	if memberSet["universal"] {
		t.Error("canonical name 'universal' should not appear in members list")
	}
}

func TestGroupedProjectTargets_SinglePathNotGrouped(t *testing.T) {
	grouped := GroupedProjectTargets()

	// cursor has a unique path (.cursor/skills), should not have members
	for _, g := range grouped {
		if g.Name == "cursor" {
			if len(g.Members) != 0 {
				t.Errorf("cursor should have no members, got %v", g.Members)
			}
			return
		}
	}

	t.Error("cursor not found in GroupedProjectTargets result")
}

func TestGroupedProjectTargets_NoDuplicatePaths(t *testing.T) {
	grouped := GroupedProjectTargets()

	seen := make(map[string]bool)
	for _, g := range grouped {
		if seen[g.Path] {
			t.Errorf("duplicate path %q in GroupedProjectTargets", g.Path)
		}
		seen[g.Path] = true
	}
}

func TestGroupedProjectTargets_MembersAreSorted(t *testing.T) {
	grouped := GroupedProjectTargets()

	for _, g := range grouped {
		if len(g.Members) < 2 {
			continue
		}
		for i := 1; i < len(g.Members); i++ {
			if g.Members[i] < g.Members[i-1] {
				t.Errorf("members of %q not sorted: %v", g.Name, g.Members)
				break
			}
		}
	}
}

func TestLookupProjectTarget_Alias(t *testing.T) {
	// Canonical name should resolve
	tc, ok := LookupProjectTarget("claude")
	if !ok {
		t.Fatal("LookupProjectTarget should find canonical name 'claude'")
	}
	if tc.Path == "" {
		t.Error("expected non-empty path for claude")
	}

	// Alias should also resolve to the same target
	tcAlias, ok := LookupProjectTarget("claude-code")
	if !ok {
		t.Fatal("LookupProjectTarget should find alias 'claude-code'")
	}
	if tcAlias.Path != tc.Path {
		t.Errorf("alias path %q != canonical path %q", tcAlias.Path, tc.Path)
	}

	// Unknown name should not resolve
	_, ok = LookupProjectTarget("nonexistent-tool")
	if ok {
		t.Error("LookupProjectTarget should not find unknown name")
	}
}
