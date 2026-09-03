# U.S. Cyclist Crash Monitor — Fresh 1.0

A Flask web app that searches multiple news feeds for U.S. fatal and serious-injury crashes involving cyclists and motor vehicles.

## Render

Build command:
`pip install -r requirements.txt`

Start command:
`gunicorn --bind 0.0.0.0:$PORT app:app`

The scanner is designed to avoid the previous Render timeout problem: news requests run in parallel with short per-request timeouts, and duplicate detection uses fast token comparison rather than repeated expensive sequence matching.

## Local

`python app.py`

Open `http://127.0.0.1:5000`.
