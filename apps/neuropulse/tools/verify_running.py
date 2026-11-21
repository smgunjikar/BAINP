"""Verify the local running NeuroPulse frontend against the installed assets."""
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1] / 'frontend'
ROUTES = {
    '/neuropulse?mode=active': 'index.html',
    '/neuropulse?mode=demo': 'index.html',
    '/neuropulse.js': 'app.js',
    '/neuropulse.css': 'style.css',
    '/neuropulse-demo.json': 'demo.json',
    '/neuropulse-research-example.json': 'research-example.json',
    '/neuropulse-benchmark.json': 'benchmark.json',
}

def main():
    client = build_opener(ProxyHandler({}))
    for route, filename in ROUTES.items():
        with client.open('http://127.0.0.1:3000' + route, timeout=4) as response:
            if response.read() != (ROOT / filename).read_bytes():
                raise ValueError(f'{route} differs from the installed project asset.')
    print('PASS: Port 3000 serves both Replay Studio 3 views and their matching assets.')

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f'NeuroPulse live check failed: {error}')
