# Deploy SleepSense backend on Oracle Cloud (Always Free)

Permanent, always-on, persistent hosting for the `auth` + `analytics` services.

## 1. Create the VM (Oracle Cloud Console)
1. Sign up at <https://cloud.oracle.com> (needs a card for verification — not charged).
2. **Compute → Instances → Create instance.**
   - **Image:** Canonical Ubuntu 22.04
   - **Shape:** `VM.Standard.A1.Flex` (Ampere/ARM, **Always Free**) — 1–2 OCPU, 6–12 GB RAM is plenty. If you see *“out of capacity,”* try a different Availability Domain or region.
   - Add your **SSH public key** (download/keep the private key).
3. After it boots, note the **Public IP address**.

## 2. Open the ports (TWO firewalls — both required)
**a) OCI Security List (cloud side):**
VCN → your subnet → Security List → **Add Ingress Rules** (x2):
- Source `0.0.0.0/0`, IP Protocol TCP, **Destination port 8001**
- Source `0.0.0.0/0`, IP Protocol TCP, **Destination port 8002**

**b) VM firewall (OS side):** handled automatically by `setup-oracle.sh` (the classic Oracle gotcha — the OS blocks everything but SSH until you add iptables ACCEPT rules).

## 3. Deploy
SSH in (`ssh -i <your-key> ubuntu@<PUBLIC_IP>`) and run:

```bash
curl -fsSL https://raw.githubusercontent.com/Aman196agrawal/SleepSense/aman/dev/deploy/setup-oracle.sh | bash
```

This installs Docker, opens the OS firewall, clones the repo, generates a shared
`SECRET_KEY`, and starts both services with persistent SQLite volumes and
`restart: unless-stopped` (they come back on reboot).

## 4. Verify
From your laptop:
```
curl http://<PUBLIC_IP>:8001/health   # {"status":"ok","service":"auth-service"}
curl http://<PUBLIC_IP>:8002/health   # {"status":"ok","service":"analytics-service"}
```

Then send both URLs (`http://<PUBLIC_IP>:8001` and `:8002`) to bake into the APK.

## Notes
- **HTTP (not HTTPS):** fine to start; the app already allows cleartext. For real
  HTTPS later, point a domain at the IP and put Caddy in front (auto Let's Encrypt).
- **Updates:** `cd ~/SleepSense && git pull && cd deploy && docker compose -f docker-compose.oracle.yml --env-file .env up -d --build`
- **Data** persists in the `auth-data` / `analytics-data` Docker volumes.
