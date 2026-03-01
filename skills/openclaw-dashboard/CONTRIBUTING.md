# Contributing to OpenClaw Dashboard

Thanks for your interest in contributing!

## How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## Guidelines

- **Zero-dependency constraint** — no npm, no pip, no CDN, no external fonts, no build tools. The frontend is pure HTML/CSS/JS in a single `index.html`. The backend uses Python stdlib only.
- Test on both desktop and mobile
- Update README if adding new features
- Follow existing code style
- **Theme testing** — when changing any CSS (colors, variables, layout), test with all 6 built-in themes (3 dark + 3 light). Switch themes via the 🎨 button and verify nothing breaks visually.
- **Chart testing** — when modifying chart rendering or `dailyChart` data, test both 7-day and 30-day views. Verify all 3 charts (cost trend, model breakdown, sub-agent activity) render correctly with both time ranges.

## Ideas for Contributions

- [ ] Light theme preset
- [ ] CSV export for token usage
- [ ] Session details modal
- [ ] Cron history sparklines
- [ ] Linux systemd service (alternative to macOS LaunchAgent)
- [ ] Docker container

## Questions?

Open an issue or join the [OpenClaw Discord](https://discord.com/invite/clawd).
