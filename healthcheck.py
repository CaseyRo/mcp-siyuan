import sys
import urllib.request
import urllib.error

try:
    urllib.request.urlopen("http://localhost:8000/health", timeout=3)
    sys.exit(0)
except urllib.error.HTTPError as ex:
    sys.exit(0 if ex.code == 503 else 1)
except Exception:
    sys.exit(1)
