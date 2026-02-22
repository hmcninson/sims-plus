#!/usr/bin/env bash
# ============================================================
# SIMS Plus - dnsmasq Setup (macOS)
# ============================================================
# Alternative to /etc/hosts for teams. Resolves ALL *.localhost
# to 127.0.0.1 without individual entries.
#
# Usage:
#   chmod +x scripts/setup-dnsmasq.sh
#   ./scripts/setup-dnsmasq.sh
# ============================================================

set -euo pipefail

echo "============================================================"
echo "SIMS Plus - dnsmasq Setup (macOS)"
echo "============================================================"
echo ""

# Check if on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "This script is for macOS only."
    echo "On Linux, *.localhost typically resolves to 127.0.0.1 by default."
    exit 0
fi

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Homebrew is required. Install from https://brew.sh"
    exit 1
fi

# Install dnsmasq
echo "Installing dnsmasq..."
brew install dnsmasq

# Configure dnsmasq to resolve *.localhost to 127.0.0.1
DNSMASQ_CONF="$(brew --prefix)/etc/dnsmasq.conf"
if ! grep -q "address=/localhost/127.0.0.1" "${DNSMASQ_CONF}" 2>/dev/null; then
    echo "" >> "${DNSMASQ_CONF}"
    echo "# SIMS Plus - Resolve *.localhost to 127.0.0.1" >> "${DNSMASQ_CONF}"
    echo "address=/localhost/127.0.0.1" >> "${DNSMASQ_CONF}"
    echo "Added localhost resolution to dnsmasq config."
else
    echo "dnsmasq already configured for *.localhost."
fi

# Start dnsmasq service
echo "Starting dnsmasq service..."
sudo brew services start dnsmasq

# Create resolver directory
sudo mkdir -p /etc/resolver

# Create resolver file for .localhost TLD
echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/localhost > /dev/null

echo ""
echo "Done! dnsmasq is running."
echo ""
echo "Verify with:"
echo "  dig presec.localhost @127.0.0.1"
echo "  ping -c 1 presec.localhost"
echo ""
echo "Any subdomain of .localhost will now resolve to 127.0.0.1:"
echo "  http://presec.localhost"
echo "  http://achimota.localhost"
echo "  http://anyname.localhost"
