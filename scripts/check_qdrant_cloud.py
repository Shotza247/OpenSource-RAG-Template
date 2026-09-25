"""Read-only Qdrant Cloud connectivity check using an isolated private profile."""
import json
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import dotenv_values


def main():
    root = Path(__file__).resolve().parents[1]
    values = dotenv_values(root / '.env.qdrant-cloud')
    url = (values.get('QDRANT_CLOUD_URL') or '').strip().rstrip('/')
    key = (values.get('QDRANT_CLOUD_API_KEY') or '').strip()
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or not parsed.hostname
            or not parsed.hostname.endswith('.cloud.qdrant.io')
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path):
        print('Invalid cloud URL: use the HTTPS Qdrant Cloud cluster origin.')
        return 1
    if not key:
        print('Cloud check pending: enter QDRANT_CLOUD_API_KEY privately in .env.qdrant-cloud.')
        return 2
    try:
        response = requests.get(url + '/collections', headers={'api-key': key},
                                timeout=(10, 30), allow_redirects=False)
    except requests.RequestException as error:
        print('Connection failed (' + type(error).__name__ + '). No credentials were printed.')
        return 1
    if response.status_code != 200:
        print(f'Cloud check failed: HTTP {response.status_code}. Check cluster status and database key permissions.')
        return 1
    try:
        names = sorted(item['name'] for item in response.json()['result']['collections'])
    except (ValueError, KeyError, TypeError):
        print('Cloud check failed: unexpected response format.')
        return 1
    print(json.dumps({'status': 'authenticated_read_success', 'host': parsed.hostname,
                      'collections': names, 'writes_performed': False}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
