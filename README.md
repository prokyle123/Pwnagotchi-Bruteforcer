<p align="center">
  <img src="assets/live-performance-snapshot.png" alt="Live Pwnagotchi BruteForcer performance snapshot showing processed captures, throughput, and job telemetry" width="100%">
</p>

<h1 align="center">Pwnagotchi BruteForcer</h1>

<p align="center">
  <strong>Turn a Pwnagotchi into a local Command Center for capture triage, queue control, throughput telemetry, and job history.</strong>
</p>

<p align="center">
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/version-3.3.0-65baff?style=for-the-badge" alt="Version 3.3.0"></a>
  <img src="https://img.shields.io/badge/dashboard-port%205000-0b1724?style=for-the-badge&logo=flask&logoColor=white" alt="Dashboard port 5000">
  <img src="https://img.shields.io/badge/platform-Pwnagotchi%20%2F%20Raspberry%20Pi-1a496b?style=for-the-badge" alt="Pwnagotchi Raspberry Pi">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-193b5c?style=for-the-badge" alt="GPL-3.0 license"></a>
</p>

> **Authorized-use only.** This project is for recovery testing, security assessment, and lab work involving wireless networks and capture files you own or have explicit permission to assess. Do not use it on networks or credentials you are not authorized to test.

## Not another “set it and forget it” plugin

BruteForcer gives a Pwnagotchi a real local control panel instead of leaving you with a pile of captures, terminal output, and guesswork.

It watches your capture directory, processes one queued job at a time, records what happened, and puts the useful stuff on one dashboard:

```text
capture triage → queue decision → active job → measured performance → job history
```

The Command Center is served locally at:

```text
http://<your-pwnagotchi-ip>:5000/
```

No cloud dashboard. No account. No extra machine required for the local view.

## Live snapshot

The image at the top is a real Pi run. It shows the performance panel with processed captures, measured words per second, workload progress, and current job duration.

The project also includes richer pages for queue control, capture triage, reporting, and Mutator Lab inspection.

## Dashboard tour

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>Command Center</h3>
      <img src="assets/command-center-overview.svg" alt="Representative Command Center overview" width="100%">
      <p>See the active job, queue, current throughput, system health, fan telemetry, progress history, and quick job actions without hunting through logs.</p>
    </td>
    <td width="50%" valign="top">
      <h3>Capture Library</h3>
      <img src="assets/capture-library.svg" alt="Representative Capture Library page" width="100%">
      <p>Grade captures, spot duplicates, understand queue priority, and decide whether to requeue, defer, review, or mark a bad capture.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>Mutator Lab</h3>
      <img src="assets/mutator-lab.svg" alt="Representative Mutator Lab page" width="100%">
      <p>Inspect the active candidate budget, enabled features, candidate-family mix, recent builds, and estimated workload before it consumes Pi time.</p>
    </td>
    <td width="50%" valign="top">
      <h3>Built for the Pi you actually have</h3>
      <p>BruteForcer keeps the workflow practical for a small Pwnagotchi build:</p>
      <ul>
        <li>One job at a time instead of competing processes.</li>
        <li>Temperature, RAM, swap, load, and fan RPM visible in the same place.</li>
        <li>Measured throughput instead of blindly trusting terminal redraw text.</li>
        <li>Persistent state and job history so a reboot does not turn into a mystery.</li>
      </ul>
      <p><strong>It is meant to feel like a little appliance, not an unfinished script.</strong></p>
    </td>
  </tr>
</table>

> The Command Center layout and data can vary slightly by device, plugin options, and release version. The preview panels above reflect the features included in the v3.3.0 release.

## What makes it different

| Instead of... | You get... |
|---|---|
| A folder full of unknown `.pcap` files | Capture grades, duplicate grouping, queue reasons, and review actions |
| A raw terminal counter you cannot fully trust | Measured WPS based on tested-key counters and elapsed time, with unverified terminal text called out separately |
| Wondering whether the Pi is cooking itself | CPU temperature, RAM, swap, load, PWM fan percentage, and tachometer RPM in the dashboard |
| Rerunning the same capture blindly | Persistent job history, capture status, retry tracking, and queue controls |
| A giant mystery candidate list | A capped Mutator Lab with strategy, enabled features, candidate-family mix, build history, and estimated workload |
| Losing context after a crash or reboot | An active-job journal and persistent state that help make interrupted work explainable |

## Main features

### Command Center

- Local Flask dashboard on port `5000`
- Active SSID, capture, wordlist stage, retry state, and progress
- Queue controls: pause, resume, skip, defer, requeue, and mark a capture bad
- Recent activity log and job timeline
- Current, recent-average, and completed-job throughput metrics
- Compact number display for high counters such as `249.3K` and `1.3M`

### Capture Intelligence

- Capture quality grades: `A`, `B`, `C`, `D`, and `X`
- Plain-English reasons for grades and queue decisions
- Duplicate grouping with best-capture selection
- Pending, running, cracked, failed, timeout, deferred, bad, and review filters
- Capture Library page at `/captures`
- Intelligence page at `/intelligence`
- Reports page at `/reports`

### System awareness

- CPU temperature in Fahrenheit
- Free RAM, swap use, load average, and resource history
- Optional runtime governor behavior
- Fan telemetry with PWM percentage and tachometer RPM when the companion fan plugin is installed
- Current health summary next to the workload instead of buried in system commands

### Mutator Lab

- Smart, capped candidate generation designed to keep the workload predictable on a Pi
- Configurable strategy, candidate cap, years, token pairs, separators, numeric suffixes, and custom seed settings
- Candidate-family breakdown and recent build history
- Estimated pass duration based on measured device throughput
- Full Mutator Lab page at `/mutator`

### Reliability and reporting

- One-job-at-a-time processing
- Persistent progress and job history
- Retry tracking and crash-aware active-job journal
- Per-SSID history and per-wordlist analytics
- Exportable results and reports
- Optional companion fan telemetry plugin

## Quick start

1. Copy `Bruteforcer.py` to your Pwnagotchi custom plugin directory.
2. Add the `main.plugins.Bruteforcer.*` options from [`config.example.toml`](config.example.toml) to `/etc/pwnagotchi/config.toml`.
3. Restart Pwnagotchi.
4. Open `http://<your-pwnagotchi-ip>:5000/`.

The plugin filename and config prefix are intentionally case-sensitive:

```toml
main.plugins.Bruteforcer.enabled = true
```

Use the full device install and upgrade notes here:

- [Install / upgrade guide](docs/UPGRADING.md)
- [Verification checklist](docs/VERIFICATION.md)
- [GitHub update notes](docs/GITHUB_UPDATE.md)
- [Complete changelog](CHANGELOG.md)

## Project layout

```text
Bruteforcer.py                    # Main custom plugin
config.example.toml               # Example configuration
assets/                           # README screenshots and dashboard previews
docs/                             # Upgrade, verification, and GitHub notes
extras/fan_control_telemetry.py  # Optional fan telemetry companion
CHANGELOG.md                      # Release history
```

## Built for people who like seeing the whole system

BruteForcer is for the Pwnagotchi builder who wants more than a status line:

- See what is running now.
- Know what is queued next and why.
- See whether the device is staying healthy.
- Understand what candidate generation is configured to do.
- Keep a history that makes failures and results explainable.

## Contributing and sharing

Bug reports, improvement ideas, device screenshots, and tested configuration notes are welcome. The most useful contributions are real-world Pi results: performance, thermal behavior, dashboard screenshots, and compatibility notes from authorized lab environments.

If this project is useful, star the repository and share it with the Pwnagotchi, Raspberry Pi, and responsible wireless-security communities.

## License

This project is released under the [GNU General Public License v3.0](LICENSE).
