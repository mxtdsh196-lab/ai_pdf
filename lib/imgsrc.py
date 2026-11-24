# -*- coding: utf-8 -*-
"""从 URL / 关键词取图，下载到本地缓存，供 collage 用。

为什么要下载而不能直接给 Typst URL：
实测 `#image("https://picsum.photos/800/600")` 报
`file not found (searched at /tmp/url/https:/picsum.photos/800/600)`
—— Typst 把 URL 当相对路径拼到 root 下。所以必须 Python 侧下载成文件。

三个源的分工（2026-11-24 实测）：
  wikimedia  真搜索 + 可过滤 CC0，但偏「文献级」照片   ✅ 商用安全
  wpphotos   社区日常摄影，语义准、风格自然          ✅ CC0，首选
  picsum     免 key、seed 稳定，但 seed 不是关键词         ⚠️ 只能当氛围图
  dmoe       二次元随机图，授权不明                      ⚠️ 慎用

实测失效的（别再试）：
  loremflickr   http 500
  t.alcy.cc     http 404
  stockcake     http 403（反爬）
  openverse     http 000（连不上）
  pixabay/pexels 必须 key
"""

import os
import re
import json
import hashlib

try:
    import urllib.request as _req
    import urllib.parse as _url
except Exception:
    _req = None
    _url = None


CACHE_DIR = '/sdcard/Download/.ai_pdf_imgcache'
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')


def _ensure_dir():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        return True
    except Exception:
        return False


def _cache_path(key, ext='jpg'):
    h = hashlib.md5(key.encode('utf-8')).hexdigest()[:12]
    return os.path.join(CACHE_DIR, '%s.%s' % (h, ext))


def _download(url, dest, timeout=30):
    """下载到 dest。返回 True 表示拿到有效图片。"""
    if _req is None:
        return False
    try:
        r = _req.Request(url, headers={'User-Agent': UA, 'Accept': 'image/*,*/*'})
        with _req.urlopen(r, timeout=timeout) as resp:
            if getattr(resp, 'status', 200) != 200:
                return False
            raw = resp.read()
        if len(raw) < 512:
            return False
        # 必须真是图片：JPEG/PNG/GIF/WEBP 魔数
        if not (raw[:3] == b'\xff\xd8\xff' or raw[:8] == b'\x89PNG\r\n\x1a\n'
                or raw[:6] in (b'GIF87a', b'GIF89a')
                or raw[:4] == b'RIFF'):
            return False
        with open(dest, 'wb') as f:
            f.write(raw)
        return True
    except Exception:
        return False


# ---------------- Wikimedia（真搜索 + CC0 过滤） ----------------

_WM_API = 'https://commons.wikimedia.org/w/api.php'


def wikimedia(keyword, width=1600, cc0_only=True, timeout=30):
    """按关键词搜 Wikimedia，默认只要 CC0。

    返回 dict: {path, title, license, artist, page} 或 None
    """
    if _req is None or not keyword:
        return None
    q = 'filetype:bitmap ' + str(keyword)
    if cc0_only:
        q += ' incategory:CC-Zero'
    params = {
        'action': 'query', 'format': 'json',
        'generator': 'search', 'gsrsearch': q, 'gsrlimit': '5',
        'gsrnamespace': '6',
        'prop': 'imageinfo', 'iiprop': 'url|extmetadata',
        'iiurlwidth': str(int(width)),
    }
    api = _WM_API + '?' + _url.urlencode(params)
    key = 'wm|%s|%s|%s' % (keyword, width, cc0_only)
    dest = _cache_path(key, 'jpg')
    meta_path = dest + '.json'

    if os.path.exists(dest) and os.path.getsize(dest) > 4096:
        try:
            return json.load(open(meta_path, encoding='utf-8'))
        except Exception:
            pass

    try:
        r = _req.Request(api, headers={'User-Agent': UA})
        with _req.urlopen(r, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8', 'replace'))
    except Exception:
        return None

    pages = (data.get('query') or {}).get('pages') or {}
    if not pages:
        return None

    if not _ensure_dir():
        return None

    # 优先 CC0 / PD
    def lic_of(ii):
        md = ii.get('extmetadata') or {}
        return str((md.get('LicenseShortName') or {}).get('value') or '')

    cands = []
    for _, v in pages.items():
        ii = (v.get('imageinfo') or [{}])[0]
        url = ii.get('thumburl') or ii.get('url')
        if not url:
            continue
        cands.append((lic_of(ii), v.get('title') or '', url, ii))
    if not cands:
        return None
    cands.sort(key=lambda x: 0 if ('CC0' in x[0] or 'Public domain' in x[0]) else 1)

    for lic, title, url, ii in cands:
        if _download(url, dest, timeout):
            md = ii.get('extmetadata') or {}
            info = {
                'path': dest,
                'source': 'wikimedia',
                'title': title,
                'license': lic,
                'artist': re.sub(r'<[^>]+>', '',
                                 str((md.get('Artist') or {}).get('value') or ''))[:80],
                'page': ii.get('descriptionurl') or '',
            }
            try:
                json.dump(info, open(meta_path, 'w', encoding='utf-8'), ensure_ascii=False)
            except Exception:
                pass
            return info
    return None


# ---------------- picsum（免 key，氛围图） ----------------

def picsum(seed, width=1200, height=800, grayscale=False, blur=None, timeout=30):
    """picsum 随机图。seed 只保证「同一 seed 每次同一张」，不是关键词。

    返回 dict 或 None
    """
    if _req is None:
        return None
    key = 'ps|%s|%s|%s|%s|%s' % (seed, width, height, grayscale, blur)
    dest = _cache_path(key, 'jpg')
    if os.path.exists(dest) and os.path.getsize(dest) > 4096:
        return {'path': dest, 'source': 'picsum', 'license': 'Unsplash License'}

    if not _ensure_dir():
        return None
    s = str(seed or 'default').strip() or 'default'
    url = 'https://picsum.photos/seed/%s/%d/%d' % (_url.quote(s), int(width), int(height))
    qs = []
    if grayscale:
        qs.append('grayscale')
    if blur:
        qs.append('blur=%d' % max(1, min(10, int(blur))))
    if qs:
        url += '?' + '&'.join(qs)
    if _download(url, dest, timeout):
        return {'path': dest, 'source': 'picsum', 'url': url,
                'license': 'Unsplash License (free to use)'}
    return None



# ---------------- WordPress Photo Directory（免 key，CC0，语义准） ----------------

_WP_SEARCH = 'https://wordpress.org/photos/search/%s/'

# 缩略图 URL 形如 .../xxx-300x225.jpeg，去掉 -WxH 就是原图。
# 字符类里避开引号，用 \x22 \x27 表示，避免和 Python 字符串引号冲突。
_WP_IMG_RE = r'https://pd\.w\.org/[^\s\x22\x27<>]+\.(?:jpe?g|png)'


def wpphotos(keyword, width=1600, timeout=30):
    """搜 wordpress.org/photos（全站 CC0，无需署名）。

    为什么加这个源：
    - Wikimedia 的图是「文献级」（搜 coffee cup 得到 18 世纪陶瓷藏品），不适合杂志排版
    - WordPress Photo Directory 是社区日常摄影，语义准、贴近真实使用场景
    - 实测无 Cloudflare 拦截（pxhere / stocksnap / creazilla 的 403 都是 CF 挑战）
    - 原图可达 5712x4284，铺 267mm 约 543dpi
    """
    if _req is None or not keyword:
        return None
    import re as _re
    kw = str(keyword).strip()
    # wordpress.org/photos 的多词搜索经常返回 0 结果
    # （实测 'snow mountain' 完全空，而 'snow' 有 1327 张）。
    # 所以多词时只用第一个词，至少能拿到图。
    _first = kw.replace(',', ' ').split()
    _kw1 = _first[0] if _first else kw
    url = _WP_SEARCH % _url.quote(_kw1.replace(' ', '-'))
    key = 'wp|%s|%s' % (kw, width)
    dest = _cache_path(key, 'jpg')
    meta_path = dest + '.json'
    if os.path.exists(dest) and os.path.getsize(dest) > 4096:
        try:
            return json.load(open(meta_path, encoding='utf-8'))
        except Exception:
            pass
    try:
        r = _req.Request(url, headers={'User-Agent': UA})
        with _req.urlopen(r, timeout=timeout) as resp:
            html = resp.read().decode('utf-8', 'replace')
    except Exception:
        return None

    hits = _re.findall(_WP_IMG_RE, html)
    if not hits:
        return None
    if not _ensure_dir():
        return None

    # 优先原图（去掉 -WxH 后缀），失败退回缩略图
    for cand in hits[:3]:
        origin = _re.sub(r'-\d+x\d+(\.(?:jpe?g|png))$', r'\1', cand)
        for u in (origin, cand):
            if _download(u, dest, timeout):
                info = {'path': dest, 'source': 'wordpress-photos',
                        'license': 'CC0', 'title': '', 'url': u}
                try:
                    json.dump(info, open(meta_path, 'w', encoding='utf-8'),
                              ensure_ascii=False)
                except Exception:
                    pass
                return info
    return None


# ---------------- 统一入口 ----------------

def fetch(spec, width=1600):
    """统一取图。

    spec 形式：
      @wikimedia:雪山          搜 Wikimedia CC0
      @picsum:night            随机（seed=night，非关键词）
      @picsum:night:gray       灰阶
      直接给绝对路径            原样返回
    """
    s = str(spec or '').strip()
    if not s:
        return None

    # ★ 不要用 @ 开头：pandoc 会把 @xxx 解析成 Citation 节点，
    # md2typst 只处理 Str，内容会整段消失（实测 para 变成 'img| |0,0|...'）。
    # 用 src: 前缀避开 Markdown 语法。
    # 下划线当空格（与 font= 的写法一致）。
    low = s.lower()
    if low.startswith('src:') or low.startswith('@'):
        body = s.split(':', 1)[1] if ':' in s else s[1:]
        body = body.replace('_', ' ').strip()
        bl = body.lower()
        if bl.startswith('wpphoto:') or bl.startswith('wp:'):
            return wpphotos(body.split(':', 1)[1].strip(), width=width)
        if bl.startswith('wpphoto:') or bl.startswith('wp:'):
            return wpphotos(body.split(':', 1)[1].strip(), width=width)
        if bl.startswith('wpphoto:') or bl.startswith('wp:'):
            return wpphotos(body.split(':', 1)[1].strip(), width=width)
        if bl.startswith('wikimedia:'):
            return wikimedia(body.split(':', 1)[1].strip(), width=width)
        if bl.startswith('picsum:'):
            rest = body.split(':', 1)[1].strip()
            gray = rest.lower().endswith(':gray')
            if gray:
                rest = rest[:-5]
            return picsum(rest, width=width, height=int(width * 0.667), grayscale=gray)
        return None
    return s if os.path.exists(s) else None