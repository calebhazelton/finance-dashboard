# Deployment

This app runs on a Raspberry Pi via **waitress** (production WSGI server),
managed by **systemd** (auto-start on boot, auto-restart on crash), fronted
by **nginx** (so the site is reachable at `http://pihome.local` on port 80
instead of `http://pihome.local:5000`).

## Files

- `deploy/finance-dashboard.service` — the systemd unit. Lives on the Pi at
  `/etc/systemd/system/finance-dashboard.service`.
- `deploy/nginx-finance-dashboard.conf` — the nginx reverse proxy config.
  Lives on the Pi at `/etc/nginx/sites-available/finance-dashboard`.
- `scripts/start-finance`, `stop-finance`, `restart-finance` — thin wrappers
  around `systemctl` for the app service. Installed on the Pi at
  `/usr/local/bin/` so they're runnable from anywhere as plain commands.
- `scripts/update-finance` — stops the app, `git pull`s the latest code,
  reinstalls any changed Python dependencies, and starts the app back up.
  This is the command you run on the Pi after pushing changes from your
  laptop.

These are checked into git as the source of truth. The actual files in
`/etc/` and `/usr/local/bin/` on the Pi are copies -- if the Pi's SD card
ever needs to be rebuilt, this folder is what you reinstall from.

## One-time Pi setup (already done, documented for reference / disaster recovery)

```bash
# systemd service
sudo cp deploy/finance-dashboard.service /etc/systemd/system/finance-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable --now finance-dashboard

# nginx reverse proxy
sudo apt install nginx -y
sudo cp deploy/nginx-finance-dashboard.conf /etc/nginx/sites-available/finance-dashboard
sudo ln -sf /etc/nginx/sites-available/finance-dashboard /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# convenience scripts
sudo cp scripts/* /usr/local/bin/
sudo chmod +x /usr/local/bin/start-finance /usr/local/bin/stop-finance /usr/local/bin/restart-finance /usr/local/bin/update-finance
```

## Day-to-day update workflow

On your laptop:
```bash
# make changes, test locally with `python3 app.py`
git add -A
git commit -m "Describe the change"
git push origin main
```

On the Pi (over SSH):
```bash
update-finance
```

That's the whole loop.
