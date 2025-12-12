#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="bruteforce"
PLUGIN_FILE="${PLUGIN_NAME}.py"
CONFIG_SNIPPET_FILE="config.toml"

echo "======================================="
echo "  Pwnagotchi BruteForcer Installer"
echo "======================================="

# Must be root
if [[ "$EUID" -ne 0 ]]; then
  echo "[!] Please run this script as root, e.g.:"
  echo "    sudo ./install.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "$SCRIPT_DIR/$PLUGIN_FILE" ]]; then
  echo "[!] ${PLUGIN_FILE} not found in $SCRIPT_DIR"
  echo "    Make sure bruteforce.py is in the same folder as install.sh."
  exit 1
fi

# Try to detect a good plugin directory
CANDIDATES=(
  "/usr/local/share/pwnagotchi/custom-plugins"
  "/usr/local/share/pwnagotchi/installed-plugins"
  "/etc/pwnagotchi/custom-plugins"
)

PLUGIN_DIR=""

for d in "${CANDIDATES[@]}"; do
  if [[ -d "$d" ]]; then
    PLUGIN_DIR="$d"
    break
  fi
done

# Fallback: create /usr/local/share/pwnagotchi/custom-plugins
if [[ -z "$PLUGIN_DIR" ]]; then
  PLUGIN_DIR="/usr/local/share/pwnagotchi/custom-plugins"
  echo "[*] Creating plugin directory: $PLUGIN_DIR"
  mkdir -p "$PLUGIN_DIR"
fi

echo "[*] Using plugin directory: $PLUGIN_DIR"

# Copy plugin file
echo "[*] Installing ${PLUGIN_FILE} -> ${PLUGIN_DIR}"
cp "$SCRIPT_DIR/$PLUGIN_FILE" "$PLUGIN_DIR/$PLUGIN_FILE"
chmod 644 "$PLUGIN_DIR/$PLUGIN_FILE" || true
chown root:root "$PLUGIN_DIR/$PLUGIN_FILE" 2>/dev/null || true

CONFIG_FILE="/etc/pwnagotchi/config.toml"

if [[ -f "$CONFIG_FILE" ]]; then
  # Ensure main.custom_plugins points at our plugin dir (if not already set)
  if ! grep -q "^main\.custom_plugins" "$CONFIG_FILE"; then
    echo "[*] Setting main.custom_plugins in $CONFIG_FILE"
    printf '\n# Custom plugins directory (added by BruteForcer installer)\n' >> "$CONFIG_FILE"
    printf 'main.custom_plugins = "%s"\n' "$PLUGIN_DIR" >> "$CONFIG_FILE"
  else
    echo "[*] main.custom_plugins already set in $CONFIG_FILE (leaving as-is)"
  fi

  # Add plugin config if it's not there yet
  if grep -q "main.plugins.${PLUGIN_NAME}" "$CONFIG_FILE"; then
    echo "[*] BruteForcer config already present in $CONFIG_FILE (not modifying)"
  else
    if [[ -f "$SCRIPT_DIR/$CONFIG_SNIPPET_FILE" ]]; then
      echo "[*] Appending BruteForcer config from $CONFIG_SNIPPET_FILE to $CONFIG_FILE"
      printf '\n# === BruteForcer plugin configuration (added by installer) ===\n' >> "$CONFIG_FILE"
      cat "$SCRIPT_DIR/$CONFIG_SNIPPET_FILE" >> "$CONFIG_FILE"
    else
      echo "[!] $CONFIG_SNIPPET_FILE not found in $SCRIPT_DIR"
      echo "    You will need to add the plugin config to $CONFIG_FILE manually."
    fi
  fi
else
  echo "[!] $CONFIG_FILE not found!"
  echo "    Skipping automatic config update. Add the plugin config manually."
fi

echo
echo "[+] BruteForcer plugin installed."
echo "[*] Next steps:"
echo "    - Reboot your Pwnagotchi OR restart the pwnagotchi service"
echo "    - Enable the plugin in the web UI if needed"
echo
echo "Use only for networks you own or have permission to test. :)"
