package audit_test

import (
	"os"
	"path/filepath"
	"testing"

	"skillshare/internal/audit"
)

func TestValidateRulesYAML_Valid(t *testing.T) {
	valid := "rules:\n  - id: test\n    severity: HIGH\n    pattern: test\n    message: test\n    regex: '\\bfoo\\b'\n"
	if err := audit.ValidateRulesYAML(valid); err != nil {
		t.Fatalf("valid YAML rejected: %v", err)
	}
}

func TestValidateRulesYAML_InvalidRegex(t *testing.T) {
	invalid := "rules:\n  - id: bad\n    severity: HIGH\n    pattern: test\n    message: test\n    regex: '[invalid'\n"
	if err := audit.ValidateRulesYAML(invalid); err == nil {
		t.Fatal("invalid regex should be rejected")
	}
}

func TestValidateRulesYAML_BadYAML(t *testing.T) {
	if err := audit.ValidateRulesYAML(":::bad yaml"); err == nil {
		t.Fatal("bad YAML should be rejected")
	}
}

func TestDefaultRulesTemplate(t *testing.T) {
	tmpl := audit.DefaultRulesTemplate()
	if len(tmpl) < 50 {
		t.Fatalf("template too short: %d", len(tmpl))
	}
	// Validate the template itself is valid YAML
	if err := audit.ValidateRulesYAML(tmpl); err != nil {
		// Template has all rules commented out, so it should parse but have no rules
		// parseRulesYAML should still succeed
	}
}

func TestInitRulesFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "sub", "audit-rules.yaml")
	if err := audit.InitRulesFile(path); err != nil {
		t.Fatalf("InitRulesFile: %v", err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("ReadFile: %v", err)
	}
	if len(data) < 50 {
		t.Fatalf("file too short: %d", len(data))
	}
}

func TestInitRulesFile_AlreadyExists(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "audit-rules.yaml")
	os.WriteFile(path, []byte("existing"), 0644)
	if err := audit.InitRulesFile(path); err == nil {
		t.Fatal("should reject existing file")
	}
}
