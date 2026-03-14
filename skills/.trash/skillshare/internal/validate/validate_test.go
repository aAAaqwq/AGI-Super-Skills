package validate

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestTargetName(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{"valid lowercase", "claude", false},
		{"valid with numbers", "claude2", false},
		{"valid with hyphen", "my-target", false},
		{"valid with underscore", "my_target", false},
		{"valid uppercase", "Claude", false},
		{"valid mixed case", "MyTarget", false},
		{"empty", "", true},
		{"starts with number", "2claude", true},
		{"reserved word add", "add", true},
		{"reserved word remove", "remove", true},
		{"reserved word list", "list", true},
		{"reserved word all", "all", true},
		{"reserved word case insensitive", "ADD", true},
		{"too long", strings.Repeat("a", 65), true},
		{"special chars at", "my@target", true},
		{"special chars space", "my target", true},
		{"special chars dot", "my.target", true},
		{"only hyphen", "-", true},
		{"starts with hyphen", "-target", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := TargetName(tt.input)
			if (err != nil) != tt.wantErr {
				t.Errorf("TargetName(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
			}
		})
	}
}

func TestPath(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{"valid absolute", "/home/user/skills", false},
		{"valid relative", "./skills", false},
		{"valid with tilde", "~/skills", false},
		{"empty", "", true},
		{"null byte", "/home/user\x00/skills", true},
		{"too long", "/" + strings.Repeat("a", 4096), true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := Path(tt.input)
			if (err != nil) != tt.wantErr {
				t.Errorf("Path(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
			}
		})
	}
}

func TestIsLikelySkillsPath(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected bool
	}{
		{"ends with skills", "/home/user/skills", true},
		{"claude skills", "/home/user/.claude/skills", true},
		{"codex skills", "/home/user/.codex/skills", true},
		{"cursor skills", "/home/user/.cursor/skills", true},
		{"gemini skills", "/home/user/.gemini/antigravity/skills", true},
		{"opencode skills", "/home/user/.config/opencode/skills", true},
		{"random directory", "/home/user/documents", false},
		{"contains skills but not ending", "/home/skills/other", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := IsLikelySkillsPath(tt.input)
			if got != tt.expected {
				t.Errorf("IsLikelySkillsPath(%q) = %v, want %v", tt.input, got, tt.expected)
			}
		})
	}
}

func TestTargetPath(t *testing.T) {
	// Create temp directory for testing
	tempDir := t.TempDir()
	existingDir := filepath.Join(tempDir, "skills")
	if err := os.MkdirAll(existingDir, 0755); err != nil {
		t.Fatalf("failed to create test dir: %v", err)
	}

	// Create a file (not a directory)
	existingFile := filepath.Join(tempDir, "file.txt")
	if err := os.WriteFile(existingFile, []byte("test"), 0644); err != nil {
		t.Fatalf("failed to create test file: %v", err)
	}

	tests := []struct {
		name        string
		path        string
		wantErr     bool
		errContains string
	}{
		{
			name:    "existing directory",
			path:    existingDir,
			wantErr: false,
		},
		{
			name:        "path does not exist",
			path:        filepath.Join(tempDir, "nonexistent"),
			wantErr:     true,
			errContains: "does not exist",
		},
		{
			name:        "path is file not directory",
			path:        existingFile,
			wantErr:     true,
			errContains: "not a directory",
		},
		{
			name:        "empty path",
			path:        "",
			wantErr:     true,
			errContains: "cannot be empty",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := TargetPath(tt.path)
			if (err != nil) != tt.wantErr {
				t.Errorf("TargetPath(%q) error = %v, wantErr %v", tt.path, err, tt.wantErr)
			}
			if tt.wantErr && tt.errContains != "" && err != nil {
				if !strings.Contains(err.Error(), tt.errContains) {
					t.Errorf("TargetPath(%q) error = %v, want error containing %q", tt.path, err, tt.errContains)
				}
			}
		})
	}
}

func TestFlatSkillName(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		// Valid flat skill names
		{"simple name", "my-skill", false},
		{"with numbers", "skill123", false},
		{"with underscore", "my_skill", false},
		{"nested separator", "team__ui", false},
		{"deep nesting", "a__b__c__d", false},
		{"tracked repo skill", "_team__frontend__ui", false},
		{"tracked simple", "_team-repo", false},

		// Invalid flat skill names
		{"empty", "", true},
		{"only _", "_", true},
		{"_ with space", "_ team", true},
		{"space in name", "my skill", true},
		{"dot in name", "my.skill", true},
		{"slash in name", "my/skill", true},
		{"too long", strings.Repeat("a", 129), true},
		{"starts with hyphen", "-skill", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := FlatSkillName(tt.input)
			if (err != nil) != tt.wantErr {
				t.Errorf("FlatSkillName(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
			}
		})
	}
}

func TestTrackedRepoName(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		// Valid tracked repo names
		{"simple", "_team", false},
		{"with hyphen", "_team-repo", false},
		{"with underscore", "_team_repo", false},
		{"with numbers", "_team123", false},
		{"company style", "_company-skills", false},

		// Invalid tracked repo names
		{"empty", "", true},
		{"only _", "_", true},
		{"no _ prefix", "team-repo", true},
		{"_ with space", "_ team", true},
		{"space in name", "_my team", true},
		{"dot in name", "_my.team", true},
		{"slash in name", "_my/team", true},
		{"too short", "_", true},
		{"too long", "_" + strings.Repeat("a", 64), true},
		{"starts with hyphen after _", "_-team", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := TrackedRepoName(tt.input)
			if (err != nil) != tt.wantErr {
				t.Errorf("TrackedRepoName(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
			}
		})
	}
}
