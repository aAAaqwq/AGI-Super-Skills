package config

import (
	"testing"

	"gopkg.in/yaml.v3"
)

func TestHubConfig_ResolveHub(t *testing.T) {
	h := HubConfig{
		Hubs: []HubEntry{
			{Label: "team", URL: "https://internal.corp/hub.json"},
			{Label: "local", URL: "./hub.json"},
		},
	}

	url, ok := h.ResolveHub("team")
	if !ok || url != "https://internal.corp/hub.json" {
		t.Errorf("ResolveHub(team) = %q, %v", url, ok)
	}

	// Case-insensitive lookup
	url, ok = h.ResolveHub("Team")
	if !ok || url != "https://internal.corp/hub.json" {
		t.Errorf("ResolveHub(Team) = %q, %v", url, ok)
	}

	_, ok = h.ResolveHub("nonexistent")
	if ok {
		t.Error("ResolveHub(nonexistent) should return false")
	}
}

func TestHubConfig_DefaultHub(t *testing.T) {
	h := HubConfig{
		Default: "team",
		Hubs: []HubEntry{
			{Label: "team", URL: "https://internal.corp/hub.json"},
		},
	}

	url, err := h.DefaultHub()
	if err != nil {
		t.Fatalf("DefaultHub() error: %v", err)
	}
	if url != "https://internal.corp/hub.json" {
		t.Errorf("DefaultHub() = %q, want https://internal.corp/hub.json", url)
	}

	// Empty default returns empty
	h2 := HubConfig{}
	url, err = h2.DefaultHub()
	if err != nil {
		t.Fatalf("empty DefaultHub() error: %v", err)
	}
	if url != "" {
		t.Errorf("empty DefaultHub() = %q, want empty", url)
	}

	// Default set but label missing → error
	h3 := HubConfig{Default: "missing"}
	_, err = h3.DefaultHub()
	if err == nil {
		t.Error("DefaultHub() with missing label should error")
	}
}

func TestHubConfig_AddHub(t *testing.T) {
	h := HubConfig{}

	if err := h.AddHub(HubEntry{Label: "test", URL: "https://example.com/hub.json"}); err != nil {
		t.Fatalf("AddHub() error: %v", err)
	}
	if len(h.Hubs) != 1 {
		t.Fatalf("len(Hubs) = %d, want 1", len(h.Hubs))
	}

	// Duplicate label
	if err := h.AddHub(HubEntry{Label: "test", URL: "https://other.com/hub.json"}); err == nil {
		t.Error("AddHub() duplicate should error")
	}

	// Empty label
	if err := h.AddHub(HubEntry{Label: "", URL: "https://x.com"}); err == nil {
		t.Error("AddHub() empty label should error")
	}

	// Empty URL
	if err := h.AddHub(HubEntry{Label: "x", URL: ""}); err == nil {
		t.Error("AddHub() empty URL should error")
	}
}

func TestHubConfig_RemoveHub(t *testing.T) {
	h := HubConfig{
		Default: "team",
		Hubs: []HubEntry{
			{Label: "team", URL: "https://internal.corp/hub.json"},
			{Label: "local", URL: "./hub.json"},
		},
	}

	if err := h.RemoveHub("team"); err != nil {
		t.Fatalf("RemoveHub() error: %v", err)
	}
	if len(h.Hubs) != 1 {
		t.Fatalf("len(Hubs) = %d, want 1", len(h.Hubs))
	}
	if h.Default != "" {
		t.Errorf("default should be cleared, got %q", h.Default)
	}

	// Remove non-default
	h2 := HubConfig{
		Default: "team",
		Hubs: []HubEntry{
			{Label: "team", URL: "a"},
			{Label: "local", URL: "b"},
		},
	}
	if err := h2.RemoveHub("local"); err != nil {
		t.Fatalf("RemoveHub(local) error: %v", err)
	}
	if h2.Default != "team" {
		t.Errorf("default should still be team, got %q", h2.Default)
	}

	// Remove nonexistent
	if err := h2.RemoveHub("nope"); err == nil {
		t.Error("RemoveHub(nope) should error")
	}
}

func TestHubConfig_HasHub(t *testing.T) {
	h := HubConfig{
		Hubs: []HubEntry{{Label: "team", URL: "x"}},
	}
	if !h.HasHub("team") {
		t.Error("HasHub(team) should be true")
	}
	if h.HasHub("other") {
		t.Error("HasHub(other) should be false")
	}
}

func TestHubConfig_YAMLRoundTrip(t *testing.T) {
	original := Config{
		Source:  "/tmp/skills",
		Targets: map[string]TargetConfig{"claude": {Path: "/tmp/claude"}},
		Hub: HubConfig{
			Default: "team",
			Hubs: []HubEntry{
				{Label: "team", URL: "https://internal.corp/hub.json"},
				{Label: "local", URL: "./hub.json"},
			},
		},
	}

	data, err := yaml.Marshal(&original)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var loaded Config
	if err := yaml.Unmarshal(data, &loaded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if loaded.Hub.Default != "team" {
		t.Errorf("hub.default = %q, want team", loaded.Hub.Default)
	}
	if len(loaded.Hub.Hubs) != 2 {
		t.Fatalf("hub.hubs len = %d, want 2", len(loaded.Hub.Hubs))
	}
	if loaded.Hub.Hubs[0].Label != "team" {
		t.Errorf("hubs[0].label = %q, want team", loaded.Hub.Hubs[0].Label)
	}
	if loaded.Hub.Hubs[1].URL != "./hub.json" {
		t.Errorf("hubs[1].url = %q, want ./hub.json", loaded.Hub.Hubs[1].URL)
	}
}

func TestHubConfig_EmptyOmitted(t *testing.T) {
	cfg := Config{
		Source:  "/tmp/skills",
		Targets: map[string]TargetConfig{},
	}

	data, err := yaml.Marshal(&cfg)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	s := string(data)
	if contains(s, "hub:") {
		t.Errorf("empty HubConfig should be omitted from YAML, got:\n%s", s)
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && searchString(s, substr)
}

func searchString(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
