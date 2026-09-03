import urllib.request
import time
import threading
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from http.server import ThreadingHTTPServer
from ui.server import TeamTrauAPIHandler

server = ThreadingHTTPServer(('127.0.0.1', 8991), TeamTrauAPIHandler)
t = threading.Thread(target=server.serve_forever, daemon=True)
t.start()
time.sleep(0.2)

paths = ['/', '/assets/app.css', '/assets/app.js', '/assets/react.production.min.js']
for p in paths:
    url = f'http://127.0.0.1:8991{p}'
    resp = urllib.request.urlopen(url)
    data = resp.read()
    ct = resp.headers.get('Content-Type')
    print(f'OK: {p} -> {resp.status} ({len(data)} bytes, {ct})')

server.shutdown()
print('SUCCESS: All static assets verified!')
