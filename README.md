# Clothing Sale Monitor

Monitors premium menswear brands for site-wide sales and sends Pushover + email alerts.

## Brands Monitored

| Brand | Threshold |
|---|---|
| Travis Matthew | 30% off |
| Rhoback | 30% off |
| Vuori | 20% off |
| Peter Millar | 20% off |
| Holderness & Bourne | 30% off |
| Lululemon | 30% off |
| Titleist | 30% off |
| Johnnie O | 30% off |
| Primo Golf | 30% off |

## Setup

```bash
git clone https://github.com/bhoogs/Clothing-Monitor.git clothing_monitor
cd clothing_monitor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Environment Variables

Set in `~/.bashrc`:
```
GEMINI_API_KEY=...
GMAIL_APP_PASSWORD=...
SENDER_EMAIL=...
RECIPIENT_EMAIL=...
PUSHOVER_USER=...
PUSHOVER_TOKEN=...
```

## Cron (7am and 7pm daily)

```
0 7 * * * /home/bhoogs/clothing_monitor/venv/bin/python /home/bhoogs/clothing_monitor/clothing_monitor.py > /dev/null 2>&1
0 19 * * * /home/bhoogs/clothing_monitor/venv/bin/python /home/bhoogs/clothing_monitor/clothing_monitor.py > /dev/null 2>&1
```
