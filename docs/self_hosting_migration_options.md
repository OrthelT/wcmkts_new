# Self-Hosting Migration Options

A research report on moving the Winter Coalition Market Stats Viewer off Streamlit
Community Cloud onto self-managed / non-walled-garden infrastructure.

**Date:** 2026-06-19 · **Budget target:** < $50/mo (ideally far less) · **Profile:**
strong Python + Bash/Linux, but first-time server/website deployment, wants to learn
without an unreasonable time sink.

---

## TL;DR — the three best options

| Rank | Option | ~Monthly cost | Effort to learn | Why it fits |
|------|--------|---------------|-----------------|-------------|
| **1** | **VPS (Hetzner / DigitalOcean) + Caddy + systemd** | **$5–6** | ~2–4 h first setup, then low | Cheapest, total control, *is* the "learn to run a server" goal. Prefers VPS. |
| **2** | **Render (managed PaaS)** | **$7** flat | ~30–60 min | Lowest-effort escape from Streamlit Cloud. Official Streamlit guide, GitHub auto-deploy, not a walled garden. |
| **3** | **Fly.io (container PaaS)** | **$3.30–6** | ~1–2 h | Cheapest always-on; teaches Docker/containers as a middle ground between VPS and full PaaS. |

**Architecture note that shapes everything below:** Streamlit runs a single persistent
Tornado server and holds **one long-lived WebSocket per browser session** — every widget
interaction round-trips over it. So **serverless function platforms cannot host it**
(see "Ruled out"). It also keeps `session_state` and `@st.cache_data` frames **in-process
RAM**, so it does **not** scale horizontally for free — a single always-on instance with a
**persistent writable disk** (for the local `wcmktprod.db` / `sdelite.db` / `buildcost.db`
Turso embedded replicas) is exactly the right shape. Budget **≥ 1 GB RAM**; 512 MB is tight
once caches warm up. [S-res-1][S-res-2][turso-1]

---

## Recommendation 1 — A VPS (best fit: you said you prefer a VPS and want to learn)

This is the option that actually delivers your secondary goal — learning to host and manage
a remote server — while also being the cheapest and least walled-in. With **Caddy** as the
reverse proxy the two genuinely fiddly parts (TLS certificates and WebSocket proxying)
collapse into ~3 lines of config, so the learning curve is real but bounded.

### Which VPS

| Provider | Tier | Price/mo | Specs | Notes |
|----------|------|----------|-------|-------|
| **Hetzner Cloud** | CAX11 (ARM) | **€4.49** (~$5) | 2 vCPU / 4 GB / 40 GB NVMe / 20 TB | Best spec/$. **Cheap tiers are EU-only** (Germany/Finland); US locations cost more and are AMD-only. [vps-1] |
| **DigitalOcean** | Basic 1 GB | **$6** | 1 vCPU / 1 GB / 25 GB / 1 TB | US-friendly, true hourly billing, **$200/60-day signup credit**, free cloud firewall. [vps-2] |
| **Linode/Akamai** | Nanode 1 GB | **$5** | 1 vCPU / 1 GB / 25 GB / 1 TB | $100 signup credit; next tier jumps to $12 (2 GB). [vps-3] |
| **OVHcloud** | VPS-1 | **~$4.54** | 2 vCPU / 4 GB / 40 GB | Best raw spec, but price requires **12-month prepay**; vCPUs burstable. [vps-4] |
| **Vultr** | HF 1 GB | **$6** | 1 vCPU / 1 GB / 25 GB NVMe | $3.50 tier exists but is 512 MB & instance-capped. [vps-5] |

**Pick:** **Hetzner CAX11** if you're EU-based or don't care where the box lives (cheapest,
4 GB RAM gives comfortable headroom). **DigitalOcean** if you want US hosting, the best docs,
and the $200 credit to experiment risk-free for two months. Either lands at **~$5–6/mo**.

### Deployment process (Caddy + systemd path — recommended for a first-timer)

Rough time: **2–4 hours hands-on** the first time, then near-zero. Ordered: [proc-1][proc-2]

1. **Provision** an Ubuntu 24.04 LTS instance; note its public IP.
2. **DNS early:** add an `A` record `yourdomain → IP` (propagates while you work). Caddy
   can't issue a TLS cert until DNS resolves to the box.
3. **Harden SSH:** create a non-root sudo user, `ssh-copy-id` your key, then set
   `PasswordAuthentication no` / `PermitRootLogin no`. Verify key login in a second
   terminal before logging out.
4. **Firewall (ufw):** default-deny inbound; allow only `OpenSSH` and `80,443/tcp`.
   **Do not expose 8501** — Streamlit binds to `127.0.0.1` and Caddy reaches it locally.
5. **Auto-patches:** `apt install unattended-upgrades fail2ban`.
6. **App runtime:** install `uv`, clone the repo, `uv sync`, drop in `.streamlit/secrets.toml`
   (Turso creds). Smoke-test: `uv run streamlit run app.py --server.address 127.0.0.1`.
7. **`.streamlit/config.toml`:** `address="127.0.0.1"`, `port=8501`, `headless=true`.
8. **systemd unit** with `Restart=always` + `enable` → survives crashes *and* reboots.
9. **Caddy** reverse proxy — the entire `Caddyfile` is:
   ```
   yourdomain.com {
       reverse_proxy 127.0.0.1:8501
   }
   ```
   Caddy then **auto-obtains + auto-renews** the Let's Encrypt cert and **handles the
   WebSocket upgrade automatically** — no header juggling. [proc-3][proc-4]
10. **Verify** `https://yourdomain.com` loads, widgets respond (WebSocket OK), valid cert.

> **Why Caddy over Nginx here:** Nginx works but you must hand-write the WebSocket headers
> (`proxy_http_version 1.1`, `Upgrade`/`Connection "upgrade"`), raise `proxy_read_timeout`,
> and run certbot separately — otherwise Streamlit hangs on a perpetual "Please wait…"
> (WebSocket close code 1006). Caddy does all of that by default. [proc-5][S-proxy-1]

### Gotchas
- **Turso replica needs the local disk** — fine on any VPS (persistent by default). Your
  existing `init_db.py` content-check + re-sync logic already handles a cold/empty file.
  [turso-1][turso-2]
- **Backups:** the Turso remote (populated by `mkts_backend`) is the source of truth, so a
  lost local `.db` just re-syncs. Add a provider snapshot (~20% of instance cost) for the
  OS/config if you want one-click restore. Litestream is only needed if you ever self-host
  the libSQL primary. [turso-3][bk-1]
- **CORS/XSRF:** at the domain root behind Caddy you can leave Streamlit's defaults on;
  don't blindly set `enableCORS=false` (XSRF silently re-enables both anyway). [S-proxy-2]

---

## Recommendation 2 — Render (lowest-effort managed option)

If after weighing it you'd rather *not* babysit an OS, Render is the cleanest jump off
Streamlit Cloud. It's a managed PaaS but **not a walled garden** — standard container/Python
app, your repo, portable away anytime. Render even publishes an **official Streamlit deploy
guide**. [paas-render-1]

- **Cost:** **$7/mo flat** for an always-on **Starter** instance (512 MB / 0.5 vCPU). The
  free tier exists but **spins down after 15 min idle** with a ~1-min cold start — fine for
  a personal demo, annoying for a dashboard you check often, so go Starter. [paas-render-2]
- **WebSockets:** fully supported (persistent process, 100-min request timeout). [paas-render-1]
- **Persistent disk:** Render Disks at **$0.25/GB/mo** for the SQLite replicas. Caveat: a
  disk pins the service to one instance and disables zero-downtime deploys (acceptable for a
  single-instance app like this). [paas-render-3]
- **Deploy:** connect GitHub → auto-redeploy on push; native Python runtime or Docker;
  automatic SSL + custom domain included. **~30–60 min** to first deploy.
- **Verdict:** least to learn, most predictable bill. ~**$7–8/mo** all-in.

---

## Recommendation 3 — Fly.io (cheapest always-on; learn containers)

A middle ground: more hands-on than Render, cheaper, and it teaches you Docker without the
full OS-admin surface of a VPS. Official Streamlit guide exists; **WebSockets "just work"**
with edge TLS. [paas-fly-1][paas-fly-2]

- **Cost:** `shared-cpu-1x` always-on — **$3.32/mo (512 MB)** or **$5.92/mo (1 GB)** +
  small egress. **No permanent free tier** anymore (just a $5 trial credit). [paas-fly-3]
- **Persistent disk:** **Fly Volumes $0.15/GB/mo**. **Critical:** the machine rootfs is
  **ephemeral and wiped on every deploy** — the `.db` replicas **must** live on a mounted
  volume, or you re-sync from scratch each deploy. [paas-fly-4]
- **Deploy:** `fly launch` generates `fly.toml` + a Dockerfile; set `headless=true` and
  internal port 8501; pin **`min_machines_running=1`** to stay always-on (Fly can otherwise
  auto-stop and cold-start). **~1–2 h** first time. [paas-fly-5]
- **Verdict:** lowest always-on price, teaches containers, but Docker-only + the ephemeral-FS
  footgun make it slightly more error-prone than Render.

### Honorable mention — Railway / Google Cloud Run
- **Railway** (~$5–10/mo, usage-based, $5 Hobby credit): nice GitHub flow and auto-TLS, but
  the bill is variable and it **caps connections at 15 min** (Streamlit reconnects, so it
  works, just noisier). A fine alternative to Render if you like its UX. [paas-rail-1]
- **Google Cloud Run** *can* run Streamlit (WebSockets GA, `min-instances=1` to stay warm),
  but the 60-min request cap, active-billing-while-connected model, and GCP's complexity make
  it **~$10–25/mo** and more to learn — not worth it here versus a $5 VPS. [sl-cr-1]

---

## Ruled out for Streamlit (don't waste time here)
- **Vercel** — serverless functions only; **cannot host a WebSocket server**. Community
  consensus: Streamlit doesn't work natively. [sl-vercel-1]
- **Cloudflare Workers / Pages** — V8-isolate functions (5-min CPU cap) and static hosting
  respectively; neither runs a persistent Python server. **Cloudflare Containers** technically
  can, but it's preview-era, scale-to-zero (cold starts), and less proven than Cloud Run.
  [sl-cf-1]

---

## Suggested path

1. **Start on Render Starter ($7)** this week to get off Streamlit Cloud in under an hour
   with zero risk — confirm the app + Turso sync behave on managed infra.
2. **In parallel, stand up a Hetzner/DigitalOcean VPS** (use DO's $200 credit) and follow the
   Caddy + systemd steps above. This is where you actually learn server ops.
3. Once the VPS is solid, **cut over and drop Render** — landing you at **~$5–6/mo** with full
   control and no walled garden. Keep the VPS provider's daily snapshot as your safety net.

This gives you an immediate, safe migration *and* the hands-on learning you asked for, for the
price of one month of overlap.

---

## Sources

**VPS pricing** — [vps-1] https://docs.hetzner.com/cloud/general/locations/ ·
https://www.bitdoze.com/hetzner-cloud-cost-optimized-plans/ · [vps-2]
https://www.digitalocean.com/pricing/droplets · [vps-3] https://www.akamai.com/cloud/pricing ·
[vps-4] https://us.ovhcloud.com/vps/ · [vps-5]
https://www.vultr.com/products/high-frequency-compute/

**VPS deploy process** — [proc-1]
https://medium.com/@paulhoke/how-to-set-up-and-harden-a-new-ubuntu-24-04-server-1929ac72161f ·
[proc-2]
https://fuzzyblog.io/blog/python/2019/11/13/making-a-streamlit-machine-learning-app-into-a-systemd-service.html ·
[proc-3] https://caddyserver.com/docs/automatic-https · [proc-4]
https://caddyserver.com/docs/caddyfile/directives/reverse_proxy · [proc-5]
https://discuss.streamlit.io/t/how-to-use-streamlit-with-nginx/378

**Streamlit proxy/resource gotchas** — [S-proxy-1]
https://github.com/streamlit/streamlit/issues/6305 · [S-proxy-2]
https://docs.streamlit.io/develop/api-reference/configuration/config.toml · [S-res-1]
https://discuss.streamlit.io/t/confused-about-how-resource-limit-scales/37922 · [S-res-2]
https://github.com/streamlit/streamlit/issues/12506

**Turso / backups** — [turso-1] https://docs.turso.tech/features/embedded-replicas · [turso-2]
https://turso.tech/blog/local-first-cloud-connected-sqlite-with-turso-embedded-replicas ·
[turso-3] https://turso.tech/pricing · [bk-1] https://litestream.io/how-it-works/

**PaaS** — [paas-render-1]
https://render.com/articles/deploy-streamlit-gradio-localhost-to-live · [paas-render-2]
https://render.com/pricing · [paas-render-3] https://render.com/docs/disks · [paas-fly-1]
https://fly.io/docs/python/frameworks/streamlit/ · [paas-fly-2]
https://fly.io/blog/websockets-and-fly/ · [paas-fly-3] https://fly.io/docs/about/pricing/ ·
[paas-fly-4] https://fly.io/docs/volumes/overview/ · [paas-fly-5]
https://community.fly.io/t/running-streamlit-apps-on-fly-io/20422 · [paas-rail-1]
https://docs.railway.com/pricing/plans

**Serverless verdicts** — [sl-vercel-1]
https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections ·
[sl-cf-1] https://developers.cloudflare.com/workers/platform/pricing/ · [sl-cr-1]
https://docs.cloud.google.com/run/docs/triggering/websockets
