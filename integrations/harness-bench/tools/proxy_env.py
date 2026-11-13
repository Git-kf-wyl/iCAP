"""Keep API hosts direct while retaining configured proxies for other destinations."""
import os
import sys
from urllib.parse import urlsplit


def configure_no_proxy(base_urls, env=None):
    env = os.environ if env is None else env
    entries = []
    for value in (env.get('NO_PROXY', ''), env.get('no_proxy', ''),
                  'localhost,127.0.0.1,::1,host.docker.internal'):
        entries.extend(item.strip() for item in value.split(',') if item.strip())
    for url in base_urls:
        if not url:
            continue
        parsed = urlsplit(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            raise ValueError('Model/judge base URL must be an absolute HTTP(S) URL')
        entries.append(parsed.hostname)
    if '*' in entries:
        value = '*'
    else:
        value = ','.join(dict.fromkeys(entries))
    env['NO_PROXY'] = env['no_proxy'] = value
    return value


if __name__ == '__main__':
    print(configure_no_proxy(sys.argv[1:]))
