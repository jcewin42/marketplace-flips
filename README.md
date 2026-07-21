# marketplace-flips

Facebook Marketplace monitoring/flipping assistant. Develop on your
Mac, deploy on the Pi.

## Local development (MacBook)

```bash
git clone <your-repo-url>
cd marketplace-flips
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real keys
python monitor.py
```

## Deploying to the Pi (one-time setup)

```bash
git clone <your-repo-url>
cd marketplace-flips
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real keys - .env is gitignored, set separately on each machine
```

Install the systemd service so it survives reboots and restarts itself
on crash:

```bash
sudo cp marketplace-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable marketplace-monitor
sudo systemctl start marketplace-monitor
```

Check it's running / view logs:

```bash
sudo systemctl status marketplace-monitor
journalctl -u marketplace-monitor -f
```

## Shipping a change

```bash
# on the Mac
git add .
git commit -m "..."
git push

# on the Pi
git pull
sudo systemctl restart marketplace-monitor
```

## Adding a new search

1. Add `search_configs/<name>.py` with a `CONFIG = SearchConfig(...)`.
2. Set `ACTIVE_SEARCH=<name>` in `.env` (or run a second instance of
   the service pointed at a different `.env` if you want multiple
   searches running at once - not set up yet, but the db/config split
   was built with that in mind).
