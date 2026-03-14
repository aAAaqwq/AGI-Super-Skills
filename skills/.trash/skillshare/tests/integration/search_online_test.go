//go:build online

package integration

import (
	"os"
	"testing"

	"skillshare/internal/testutil"
)

// TestSearch_BasicQuery runs a real GitHub search.
// Requires GITHUB_TOKEN or GH_TOKEN to be set; skips otherwise.
func TestSearch_BasicQuery(t *testing.T) {
	if os.Getenv("GITHUB_TOKEN") == "" && os.Getenv("GH_TOKEN") == "" {
		t.Skip("GITHUB_TOKEN not set, skipping search test")
	}

	sb := testutil.NewSandbox(t)
	defer sb.Cleanup()

	sb.WriteConfig(`source: ` + sb.SourcePath + `
targets: {}
`)

	result := sb.RunCLI("search", "skillshare", "--limit", "3")

	result.AssertSuccess(t)
	result.AssertAnyOutputContains(t, "skillshare")
}
