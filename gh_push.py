
import base64, json, os, sys, time, urllib.error, urllib.parse, urllib.request

TOKEN = open('/root/.gh_token').read().strip()
OWNER, REPO, BRANCH = 'mxtdsh196-lab', 'ai_pdf', 'main'
ROOT = '/root/ai_pdf_build'
API = 'https://api.github.com'
HDR = {'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json',
       'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'ai-pdf-release'}


def req(method, path, body=None, raw=False, timeout=60):
    url = API + path if path.startswith('/') else path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            b = resp.read()
            return resp.status, (b if raw else json.loads(b.decode('utf-8', 'replace')))
    except urllib.error.HTTPError as e:
        b = e.read()
        try:
            j = json.loads(b.decode('utf-8', 'replace'))
        except Exception:
            j = {'raw': b[:300].decode('utf-8', 'replace')}
        return e.code, j
    except Exception as e:
        return 0, {'error': str(e)[:200]}


def get_sha(path):
    p = '/repos/%s/%s/contents/%s?ref=%s' % (OWNER, REPO, urllib.parse.quote(path), BRANCH)
    code, j = req('GET', p)
    return j.get('sha') if (code == 200 and isinstance(j, dict)) else None


def put_file(path, data, message):
    sha = get_sha(path)
    body = {'message': message,
            'content': base64.b64encode(data).decode('ascii'),
            'branch': BRANCH}
    if sha:
        body['sha'] = sha
    p = '/repos/%s/%s/contents/%s' % (OWNER, REPO, urllib.parse.quote(path))
    code, j = req('PUT', p, body, timeout=180)
    if code in (200, 201):
        return True, (j.get('content') or {}).get('sha', '')[:10]
    return False, '%s %s' % (code, str(j.get('message') or j)[:110])


def walk_files():
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
        for f in sorted(files):
            if f.endswith(('.pyc', '.pyo', '.log')) or f.startswith('.'):
                continue
            full = os.path.join(base, f)
            rel = os.path.relpath(full, ROOT)
            out.append(rel)
    return sorted(out)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'list'
    fs = walk_files()
    if mode == 'list':
        print('共 %d 个文件' % len(fs))
        for f in fs:
            print('  %8d  %s' % (os.path.getsize(os.path.join(ROOT, f)), f))
    elif mode == 'push':
        only = set(sys.argv[2:]) if len(sys.argv) > 2 else None
        if only:
            fs = [f for f in fs if f in only]
        print('要推 %d 个文件' % len(fs))
        ok, fail = 0, []
        for f in fs:
            data = open(os.path.join(ROOT, f), 'rb').read()
            good, info = put_file(f, data, 'update: %s' % f)
            if good:
                ok += 1
                print('  OK   %-42s %s' % (f, info))
            else:
                fail.append((f, info))
                print('  FAIL %-42s %s' % (f, info))
            time.sleep(0.3)
        print()
        print('成功 %d / 失败 %d' % (ok, len(fail)))
        for f, e in fail:
            print('  !', f, e)
