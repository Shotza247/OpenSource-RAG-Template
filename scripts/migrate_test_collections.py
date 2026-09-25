"""Copy the two approved local test collections; never overwrite a destination."""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import dotenv_values

SOURCE = 'http://127.0.0.1:6334'
DESTINATION = 'https://eade2c30-41c7-4705-872c-3d159f57b61f.eu-central-1-0.aws.cloud.qdrant.io'
EXPECTED = {'embedding_demo-bd228c87eb28': 3, 'faq_ui_ui_smoke_test-bd228c87eb28': 1}


def call(base, path, method='GET', body=None, key=None):
    response = requests.request(method, base + path, json=body,
                                headers={'api-key': key} if key else {},
                                timeout=(10, 120), allow_redirects=False)
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f'{method} {path}: HTTP {response.status_code}')
    return response.json()['result']


def points(base, name, key=None):
    result, offset = [], None
    while True:
        body = {'limit': 100, 'with_payload': True, 'with_vector': True}
        if offset is not None:
            body['offset'] = offset
        page = call(base, f'/collections/{name}/points/scroll', 'POST', body, key)
        result.extend(page['points'])
        offset = page.get('next_page_offset')
        if offset is None:
            return sorted(result, key=lambda p: str(p['id']))


def verify_points(original, copied):
    if len(original) != len(copied):
        raise RuntimeError('Point count mismatch')
    for a, b in zip(original, copied):
        if a['id'] != b['id'] or a.get('payload') != b.get('payload'):
            raise RuntimeError('Point ID or payload mismatch')
        if len(a['vector']) != len(b['vector']) or not all(
            math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-7)
            for x, y in zip(a['vector'], b['vector'])
        ):
            raise RuntimeError('Vector mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Create and populate missing cloud collections')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = dotenv_values(root / '.env.qdrant-cloud')
    key = env.get('QDRANT_CLOUD_API_KEY')
    if env.get('QDRANT_CLOUD_URL', '').rstrip('/') != DESTINATION or not key:
        raise RuntimeError('Expected cloud profile and database key required')
    existing = {c['name'] for c in call(DESTINATION, '/collections', key=key)['collections']}
    if existing.intersection(EXPECTED):
        raise RuntimeError('Destination collection already exists; refusing overwrite. Inspect before retrying.')
    source = {}
    for name, count in EXPECTED.items():
        info = call(SOURCE, '/collections/' + name)
        data = points(SOURCE, name)
        if info['config']['params']['vectors'] != {'size': 384, 'distance': 'Cosine'} or len(data) != count:
            raise RuntimeError('Source changed; review before migration: ' + name)
        source[name] = (info, data)
    if not args.apply:
        print(json.dumps({'status': 'preflight_passed', 'planned_collections': EXPECTED, 'writes': False}, indent=2))
        return
    output = root / '.local' / 'migrations' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output.mkdir(parents=True, exist_ok=False)
    report = {'source': SOURCE, 'destination': DESTINATION, 'status': 'in_progress',
              'created': [], 'verified': [], 'hf_calls': 0, 'catalog_migrated': False}
    try:
        for name, (info, data) in source.items():
            path = '/collections/' + name
            call(DESTINATION, path, 'PUT', {'vectors': info['config']['params']['vectors']}, key)
            report['created'].append(name)
            for field, schema in info['payload_schema'].items():
                call(DESTINATION, path + '/index?wait=true', 'PUT',
                     {'field_name': field, 'field_schema': schema.get('params') or schema['data_type']}, key)
            call(DESTINATION, path + '/points?wait=true', 'PUT', {'points': data}, key)
            verify_points(data, points(DESTINATION, name, key))
            verify_points(data, points(SOURCE, name))
            cloud = call(DESTINATION, path, key=key)
            if cloud['config']['params']['vectors']['size'] != 384 or cloud['config']['params']['vectors']['distance'] != 'Cosine':
                raise RuntimeError('Cloud vector configuration mismatch')
            for field, schema in info['payload_schema'].items():
                if cloud['payload_schema'].get(field, {}).get('data_type') != schema['data_type']:
                    raise RuntimeError('Payload index missing or different')
            query = {'query': data[0]['vector'], 'limit': len(data), 'params': {'exact': True}}
            a = call(SOURCE, path + '/points/query', 'POST', query)['points']
            b = call(DESTINATION, path + '/points/query', 'POST', query, key)['points']
            if [p['id'] for p in a] != [p['id'] for p in b] or not all(
                math.isclose(x['score'], y['score'], abs_tol=1e-5, rel_tol=1e-5) for x, y in zip(a, b)
            ):
                raise RuntimeError('Vector query comparison failed')
            report['verified'].append({'name': name, 'points': len(data),
                'ids_payloads_vectors_verified': True, 'payload_indexes_verified': True,
                'vector_query_parity': True})
        after = {c['name'] for c in call(DESTINATION, '/collections', key=key)['collections']}
        if after != existing.union(EXPECTED):
            raise RuntimeError('Unexpected destination inventory change')
        report['status'] = 'verified'
    finally:
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'report': str(output / 'report.json'), **report}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except requests.RequestException as error:
        print('Network failure: ' + type(error).__name__ + '. Inspect the migration report before retrying.')
        raise SystemExit(1)
    except RuntimeError as error:
        print(str(error))
        raise SystemExit(1)
