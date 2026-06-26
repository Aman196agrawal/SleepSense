#!/usr/bin/env bash
# ── SleepSense backend setup for a fresh Oracle Cloud "Always Free" ARM VM ──────
# Tested on Ubuntu 22.04 (Ampere A1). Run as the default 'ubuntu' user:
#   curl -fsSL https://raw.githubusercontent.com/Aman196agrawal/SleepSense/aman/dev/deploy/setup-oracle.sh | bash
# …or copy this file to the VM and `bash setup-oracle.sh`.
set -euo pipefail

REPO="https://github.com/Aman196agrawal/SleepSense.git"
BRANCH="aman/dev"

echo "==> Installing Docker (+ compose plugin)"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi

echo "==> Opening the VM firewall for 8001/8002 (Oracle blocks these by default)"
# Insert ACCEPT rules ABOVE Oracle's catch-all REJECT in the INPUT chain.
sudo iptables -I INPUT -p tcp --dport 8001 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 8002 -j ACCEPT
# Persist across reboots
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
sudo netfilter-persistent save

echo "==> Cloning the repo"
cd ~
[ -d SleepSense ] || git clone "$REPO"
cd SleepSense
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "==> Generating a shared SECRET_KEY (.env)"
if [ ! -f deploy/.env ]; then
  echo "SECRET_KEY=$(openssl rand -hex 32)" > deploy/.env
fi

echo "==> Building + starting services"
cd deploy
sudo docker compose -f docker-compose.oracle.yml --env-file .env up -d --build

echo
echo "==> Done. Verifying locally:"
sleep 5
curl -s http://localhost:8001/health && echo
curl -s http://localhost:8002/health && echo
PUBIP=$(curl -s ifconfig.me || echo "<your-public-ip>")
echo
echo "Public endpoints (after you add OCI Security List ingress for 8001/8002):"
echo "  auth      -> http://$PUBIP:8001"
echo "  analytics -> http://$PUBIP:8002"
echo "Give those two URLs to finish the APK."
