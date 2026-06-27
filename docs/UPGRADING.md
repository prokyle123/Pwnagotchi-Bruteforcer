# Upgrading an Existing BruteForcer Install

> Use only with captures and networks you own or are explicitly authorized to assess.

This guide preserves your current progress JSON, handshake directory, wordlists, and plugin history. It does not reformat your Pwnagotchi image or replace your whole `config.toml`.

## 1. Back up before changing anything

```bash
sudo systemctl stop pwnagotchi

mkdir -p ~/pwnagotchi-bruteforcer-backups
stamp=$(date +%Y%m%d-%H%M%S)

sudo cp -a /usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py \
  ~/pwnagotchi-bruteforcer-backups/Bruteforcer.py.$stamp

sudo cp -a /etc/pwnagotchi/config.toml \
  ~/pwnagotchi-bruteforcer-backups/config.toml.$stamp

sudo cp -a /root/bruteforce_progress.json \
  ~/pwnagotchi-bruteforcer-backups/bruteforce_progress.json.$stamp 2>/dev/null || true

ls -lh ~/pwnagotchi-bruteforcer-backups/
```

## 2. Use the correct plugin filename

The current release uses:

```text
/usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py
```

The matching configuration prefix is:

```toml
main.plugins.Bruteforcer.*
```

If you still have a legacy `bruteforce.py` plugin file or a separate `main.plugins.bruteforce.enabled = true` setting, disable/remove the legacy copy only after confirming the current `Bruteforcer.py` loads successfully. Do not leave two similarly named plugin files enabled at the same time.

## 3. Replace the plugin

Copy `Bruteforcer.py` from this release package to the custom plugin directory.

### Nano paste-in method

```bash
sudo truncate -s 0 /usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py
sudo nano /usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py
```

Paste the complete file, then save with `Ctrl+O`, press `Enter`, and exit with `Ctrl+X`.

## 4. Merge configuration deliberately

Open the config:

```bash
sudo nano /etc/pwnagotchi/config.toml
```

Use `config.example.toml` as a reference. Replace matching `main.plugins.Bruteforcer.*` lines instead of adding duplicate keys.

For a Pi-friendly starting point:

```toml
main.plugins.Bruteforcer.mutator_strategy = "smart"
main.plugins.Bruteforcer.mutator_max_words = 800
main.plugins.Bruteforcer.mutator_include_base64 = false
main.plugins.Bruteforcer.mutator_include_rot13 = false
main.plugins.Bruteforcer.mutator_include_hex = false
main.plugins.Bruteforcer.mutator_include_reversed = false
main.plugins.Bruteforcer.mutator_include_case_swaps = false
```

## 5. Validate before starting

```bash
python3 -m py_compile /usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py
```

No output means the plugin passed the Python syntax check.

If your image has the Python `toml` module installed, also validate the config:

```bash
python3 - <<'PY'
import toml
toml.load('/etc/pwnagotchi/config.toml')
print('TOML syntax OK')
PY
```

## 6. Start and verify

```bash
sudo systemctl start pwnagotchi
sleep 12
sudo systemctl status pwnagotchi --no-pager
```

Open these local pages from your trusted management device:

```text
http://10.0.0.2:5000/
http://10.0.0.2:5000/captures
http://10.0.0.2:5000/intelligence
http://10.0.0.2:5000/reports
http://10.0.0.2:5000/mutator
```

## Optional fan telemetry

`extras/fan_control_telemetry.py` is the companion fan plugin that writes a small JSON status record used by the Command Center. Install it only if your existing fan hardware uses the same GPIO arrangement or after reviewing and adapting the GPIO values to your build.

## Rollback

1. Stop the service:

   ```bash
   sudo systemctl stop pwnagotchi
   ```

2. Restore the backup you made in step 1:

   ```bash
   sudo cp ~/pwnagotchi-bruteforcer-backups/Bruteforcer.py.YYYYMMDD-HHMMSS \
     /usr/local/share/pwnagotchi/custom-plugins/Bruteforcer.py

   sudo cp ~/pwnagotchi-bruteforcer-backups/config.toml.YYYYMMDD-HHMMSS \
     /etc/pwnagotchi/config.toml
   ```

3. Start it again:

   ```bash
   sudo systemctl start pwnagotchi
   ```
