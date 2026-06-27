# Pwnagotchi BruteForcer

> **Authorized-use only.** BruteForcer is intended for recovery tests, security assessments, and lab work involving Wi-Fi networks and captures you own or have explicit permission to test. Do not use it on networks or credentials you are not authorized to assess.

BruteForcer is a Pwnagotchi custom plugin that monitors a capture directory, processes WPA/WPA2 capture files with `aircrack-ng`, and provides a local, offline-friendly Command Center dashboard. Version 3.3.0 expands the original single-job workflow with capture intelligence, resource telemetry, fan status support, measured throughput reporting, queue controls, and a Mutator Lab.

## What v3.3.0 adds

- One-job-at-a-time processing with retry tracking and persistent job history.
- Local Flask Command Center at `http://<pwnagotchi-ip>:5000/`.
- Capture Library, Intelligence, Reports, and Mutator Lab pages.
- Capture quality grades, duplicate grouping, preflight checks, queue explanations, and optional adaptive ordering.
- Measured candidates-per-second telemetry based on tested-key counters and elapsed time, with unverified terminal text clearly labeled separately.
- Resource history for temperature, RAM, swap, load, WPS, and an optional runtime governor.
- Fan telemetry support: CPU temperature in Fahrenheit, PWM percent, and tachometer RPM when the companion fan plugin is installed.
- Crash-aware active-job journal, export endpoints, per-SSID history, per-wordlist analytics, and dashboard queue actions.
- Smart, capped candidate generation with an inspectable Mutator Lab and a Pi-friendly `800` candidate example budget.

## Dashboard pages

| Page | Purpose |
|---|---|
| `/` | Command Center: current job, queue, WPS, results, logs, system health, and fan telemetry. |
| `/captures` | Searchable Capture Library with status, capture grade, duplicate grouping, priority, and requeue actions. |
| `/intelligence` | Capture quality, queue reasoning, duplicate analysis, and resource trends. |
| `/reports` | Daily and weekly activity summaries, wordlist effectiveness, and job outcomes. |
| `/mutator` | Mutator strategy, cap usage, feature state, candidate-family mix, and recent build history. |
| `/networks` | Per-SSID and wordlist performance history. |

## Requirements

- A supported Pwnagotchi image with custom-plugin loading enabled.
- `aircrack-ng` installed on the Pwnagotchi.
- Python 3, Flask, and the normal Pwnagotchi Python modules.
- A configured capture directory and wordlist directory.
- Optional: the companion fan plugin in `extras/fan_control_telemetry.py` plus `pigpiod` for PWM/RPM telemetry.

## Install on the Pwnagotchi

The device uses the filename **`Bruteforcer.py`** and the config prefix **`main.plugins.Bruteforcer.*`**. Keep that capitalization consistent.

1. Back up the current plugin and stop Pwnagotchi:

   ```bash
   sudo systemctl stop pwnagotchi
   sudo cp -a /usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py \
     /usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py.backup-$(date +%Y%m%d-%H%M%S)
   ```

2. Copy or paste `Bruteforcer.py` to:

   ```text
   /usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py
   ```

3. Merge the relevant values from [`config.example.toml`](config.example.toml) into:

   ```text
   /etc/pwnagotchi/config.toml
   ```

   Do not add a second copy of an existing TOML key. Replace the existing setting instead.

4. Verify syntax, then start the service:

   ```bash
   python3 -m py_compile /usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py
   sudo systemctl start pwnagotchi
   sudo systemctl status pwnagotchi --no-pager
   ```

No output from `py_compile` means the Python syntax check passed.

For a detailed upgrade/rollback plan, read [`docs/UPGRADING.md`](docs/UPGRADING.md).

## Configuration notes

- `mutator_max_words = 800` is a practical starting point for a Pi-class device.
- `smart` orders lower-noise candidate families early within the configured cap.
- `adaptive_queue_enabled`, `dedupe_auto_skip`, and `epaper_status_mode` are off in the example so they do not unexpectedly change an established workflow.
- The dashboard reads optional fan telemetry from `/var/tmp/pwnagotchi/fan_status.json`. Without the companion fan plugin it reports fan data as unavailable; the rest of BruteForcer still works.

## Repository layout

```text
Bruteforcer.py                    Main Pwnagotchi custom plugin
config.example.toml               Merge-only configuration example
CHANGELOG.md                      Release history
extras/fan_control_telemetry.py   Optional fan telemetry companion
docs/UPGRADING.md                 Device upgrade and rollback guide
docs/GITHUB_UPDATE.md             Publishing the release to GitHub
```

## Safety and data handling

- Treat capture files, progress JSON, reports, and dashboard exports as sensitive.
- Use restrictive permissions and keep backups off-device where possible.
- The dashboard can display operational metadata and should be kept on a trusted local network.
- The plugin is designed for authorized testing only; you are responsible for ensuring your use complies with applicable law and your testing authorization.

## License

GPL-3.0-or-later. See [`LICENSE`](LICENSE).
