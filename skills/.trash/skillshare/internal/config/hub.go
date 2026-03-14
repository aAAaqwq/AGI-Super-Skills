package config

import (
	"fmt"
	"strings"
)

// ResolveHub looks up a hub URL by label. Returns the URL and true if found.
func (h *HubConfig) ResolveHub(label string) (string, bool) {
	label = strings.TrimSpace(label)
	for _, entry := range h.Hubs {
		if strings.EqualFold(entry.Label, label) {
			return entry.URL, true
		}
	}
	return "", false
}

// DefaultHub returns the URL of the default hub.
// Returns "" if no default is set (caller should fall back to community hub).
// Returns an error if default is set but the label is not found in hubs.
func (h *HubConfig) DefaultHub() (string, error) {
	if h.Default == "" {
		return "", nil
	}
	url, ok := h.ResolveHub(h.Default)
	if !ok {
		return "", fmt.Errorf("default hub %q not found in saved hubs", h.Default)
	}
	return url, nil
}

// HasHub checks if a hub with the given label exists.
func (h *HubConfig) HasHub(label string) bool {
	label = strings.TrimSpace(label)
	for _, entry := range h.Hubs {
		if strings.EqualFold(entry.Label, label) {
			return true
		}
	}
	return false
}

// AddHub adds a new hub entry. Returns an error if the label already exists.
func (h *HubConfig) AddHub(entry HubEntry) error {
	entry.Label = strings.TrimSpace(entry.Label)
	entry.URL = strings.TrimSpace(entry.URL)
	if entry.Label == "" {
		return fmt.Errorf("hub label cannot be empty")
	}
	if entry.URL == "" {
		return fmt.Errorf("hub URL cannot be empty")
	}
	if h.HasHub(entry.Label) {
		return fmt.Errorf("hub %q already exists", entry.Label)
	}
	h.Hubs = append(h.Hubs, entry)
	return nil
}

// RemoveHub removes a hub by label. Clears default if it was the removed one.
func (h *HubConfig) RemoveHub(label string) error {
	label = strings.TrimSpace(label)
	found := false
	filtered := make([]HubEntry, 0, len(h.Hubs))
	for _, entry := range h.Hubs {
		if strings.EqualFold(entry.Label, label) {
			found = true
			continue
		}
		filtered = append(filtered, entry)
	}
	if !found {
		return fmt.Errorf("hub %q not found", label)
	}
	h.Hubs = filtered
	if strings.EqualFold(h.Default, label) {
		h.Default = ""
	}
	return nil
}
