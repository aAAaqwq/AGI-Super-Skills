function parseRepo(input) {
  if (!input) return null;
  const raw = typeof input === "string" ? input.trim() : "";
  if (!raw) return null;

  if (raw.includes("github.com")) {
    try {
      const url = new URL(raw);
      const parts = url.pathname.replace(/\.git$/, "").split("/").filter(Boolean);
      if (parts.length >= 2) {
        return {
          owner: parts[0],
          name: parts[1],
          url: `https://github.com/${parts[0]}/${parts[1]}`,
        };
      }
    } catch {
      return null;
    }
  }

  const shortMatch = raw.match(/^([\w-]+)\/([\w.-]+)$/);
  if (shortMatch) {
    return {
      owner: shortMatch[1],
      name: shortMatch[2],
      url: `https://github.com/${shortMatch[1]}/${shortMatch[2]}`,
    };
  }

  return null;
}

function resolveRepo({ cliRepo, pkgRepo, envRepo }) {
  const candidate = cliRepo || envRepo || pkgRepo || "";
  const parsed = parseRepo(candidate);
  if (parsed) return parsed;
  return null;
}

module.exports = {
  parseRepo,
  resolveRepo,
};
