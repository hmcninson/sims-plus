#!/usr/bin/env bash
# ============================================================
# SIMS Plus - Local DNS Setup for Development
# ============================================================
# This script adds /etc/hosts entries for local subdomain testing.
#
# Usage:
#   chmod +x scripts/setup-local-dns.sh
#   ./scripts/setup-local-dns.sh
#
# NOTE: Modern Chrome and Firefox automatically resolve
# *.localhost to 127.0.0.1. You may not need this script
# unless you're using Safari or an older browser.
# ============================================================

set -euo pipefail

echo "============================================================"
echo "SIMS Plus - Local DNS Setup"
echo "============================================================"
echo ""

# Define test subdomains
SUBDOMAINS=(
    "presec"
    "achimota"
    "wesleyg"
    "demo"
    "test1"
)

# Check if entries already exist
if grep -q "# SIMS Plus Local Development" /etc/hosts 2>/dev/null; then
    echo "SIMS Plus entries already exist in /etc/hosts."
    echo "To update, first remove the existing entries and run again."
    echo ""
    echo "Current entries:"
    grep -A 20 "# SIMS Plus Local Development" /etc/hosts | head -20
    exit 0
fi

# Build the hosts entries
HOSTS_BLOCK="
# SIMS Plus Local Development (added by setup-local-dns.sh)
# Remove this block if you no longer need local subdomain testing."

for sub in "${SUBDOMAINS[@]}"; do
    HOSTS_BLOCK="${HOSTS_BLOCK}
127.0.0.1 ${sub}.localhost"
done

HOSTS_BLOCK="${HOSTS_BLOCK}
# End SIMS Plus Local Development
"

echo "The following entries will be added to /etc/hosts:"
echo "${HOSTS_BLOCK}"
echo ""

read -p "Proceed? (y/N) " confirm
if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
    echo "Aborted."
    exit 0
fi

# Add entries (requires sudo)
echo "${HOSTS_BLOCK}" | sudo tee -a /etc/hosts > /dev/null

echo ""
echo "Done! Entries added to /etc/hosts."
echo ""
echo "You can now access:"
for sub in "${SUBDOMAINS[@]}"; do
    echo "  http://${sub}.localhost        -> frontend (via Nginx on port 80)"
    echo "  http://${sub}.localhost:3000   -> frontend (direct, bypass Nginx)"
done
echo ""
echo "To remove these entries later, edit /etc/hosts and delete"
echo "the block between '# SIMS Plus Local Development' comments."
