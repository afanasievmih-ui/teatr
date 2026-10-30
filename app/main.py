"""Сайт материалов театрального фестиваля: оглавление, страницы для чтения и печати.

Материалы — Markdown-файлы, разложенные по разделам:
  content/<раздел>/<материал>.md   — из репозитория (сервер подтягивает git pull по таймеру, см. deploy/DEPLOY.md)
  DATA_DIR/<раздел>/<материал>.md  — загруженные через API (tools/upload.py); при совпадении имени главнее
  <раздел>/_title.txt              — название раздела (иначе имя папки)
Заголовок материала — первая строка «# …». Файлы читаются при каждом запросе, перезапуск не нужен.

Вход: пароль (TEATR_PASSWORD) или ссылка /k/<TEATR_LINK_KEY>; после входа кука на год.
Загрузка для Claude: заголовок Authorization: Bearer <TEATR_API_TOKEN>.
"""
import hashlib, hmac, html, os, re
from datetime import datetime, timezone
from pathlib import Path

import markdown
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

HERE = Path(__file__).parent
CONTENT = Path(os.environ.get('CONTENT_DIR', HERE.parent / 'content'))
DATA = Path(os.environ.get('DATA_DIR', HERE.parent / 'data'))

PASSWORD = os.environ.get('TEATR_PASSWORD', '')
LINK_KEY = os.environ.get('TEATR_LINK_KEY', '')
API_TOKEN = os.environ.get('TEATR_API_TOKEN', '')
SECRET = os.environ.get('TEATR_SECRET') or hashlib.sha256((PASSWORD + LINK_KEY + API_TOKEN).encode()).hexdigest()
COOKIE = 'teatr'
SECURE_COOKIE = os.environ.get('TEATR_SECURE_COOKIE', '1') == '1'
ID_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
MAX_MD = 2 * 1024 * 1024

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


# ---------- вход ----------
def session_value():
    return hmac.new(SECRET.encode(), b'reader-v1', hashlib.sha256).hexdigest()

def is_api(req: Request):
    h = req.headers.get('authorization', '')
    return bool(API_TOKEN) and h.startswith('Bearer ') and hmac.compare_digest(h[7:].strip(), API_TOKEN)

def is_reader(req: Request):
    c = req.cookies.get(COOKIE, '')
    return (c and hmac.compare_digest(c, session_value())) or is_api(req)

def need_api(req: Request):
    if not is_api(req): raise HTTPException(401, 'Нужен API-токен')

def logged_in(resp):
    resp.set_cookie(COOKIE, session_value(), max_age=365 * 86400, httponly=True, samesite='lax', secure=SECURE_COOKIE)
    return resp

@app.middleware('http')
async def guard(req: Request, call_next):
    p = req.url.path
    if p.startswith(('/login', '/k/', '/healthz', '/api/')) or p == '/favicon.ico' or is_reader(req):
        return await call_next(req)
    return RedirectResponse('/login?next=' + p, 303)

PAGE = '''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=PT+Sans:wght@400;700&family=PT+Serif:ital,wght@0,400;0,700;1,400&display=swap">
<style>
:root{{--bg:#f6f2ec;--paper:#fffdf9;--ink:#221a17;--muted:#6b605a;--line:#e3d9cd;--accent:#9c1f2e;--soft:#f3e6e1}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151112;--paper:#1f191a;--ink:#efe7e2;--muted:#a99d97;--line:#3a2f2f;--accent:#ef7a86;--soft:#2c1f21;color-scheme:dark}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 "PT Sans",Roboto,Arial,sans-serif}}
.wrap{{max-width:780px;margin:0 auto;padding:24px 16px 48px;display:flex;flex-direction:column;gap:14px}}
h1,h2,h3{{font-family:"PT Serif",Georgia,serif;line-height:1.2}}h1{{font-size:1.7rem;margin:0}}
.muted{{color:var(--muted);font-size:.92rem}}a{{color:var(--accent)}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;font-size:.95rem}}
.top a{{text-decoration:none}}.btn{{font:inherit;font-weight:700;padding:8px 14px;border-radius:8px;border:1px solid var(--accent);background:transparent;color:var(--accent);cursor:pointer}}
.sec h2{{font-size:1.25rem;margin:18px 0 8px;padding-bottom:6px;border-bottom:2px solid var(--accent)}}
a.item{{display:block;background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:14px 16px;color:inherit;text-decoration:none;margin-bottom:10px}}
a.item:hover{{border-color:var(--accent)}}a.item b{{font-size:1.06rem;font-family:"PT Serif",Georgia,serif}}
article{{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:20px 22px;font:17px/1.6 "PT Serif",Georgia,serif;overflow-wrap:break-word}}
article h1{{font-size:1.6rem;margin:0 0 12px}}article h2{{font-size:1.3rem;margin:28px 0 10px;color:var(--accent)}}article h3{{font-size:1.1rem;margin:20px 0 8px}}
article table{{border-collapse:collapse;width:100%;display:block;overflow-x:auto}}article td,article th{{border:1px solid var(--line);padding:6px 8px;vertical-align:top}}
article blockquote{{margin:12px 0;padding:4px 14px;border-left:3px solid var(--accent);background:var(--soft)}}
article hr{{border:0;border-top:1px solid var(--line);margin:24px 0}}article li{{margin:4px 0}}
.toc{{background:var(--soft);border-radius:12px;padding:12px 16px;font-size:.95rem}}.toc ul{{margin:4px 0;padding-left:20px}}.toc>ul{{padding-left:4px;list-style:none}}
form{{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:18px;display:flex;flex-direction:column;gap:10px}}
input,button{{font:inherit;padding:10px 12px;border-radius:8px;border:1px solid var(--line);background:var(--paper);color:var(--ink);min-height:44px}}
form button{{background:var(--accent);color:#fff;border:0;font-weight:700}}.err{{color:#c22}}
@media print{{
  :root{{--ink:#000;--paper:#fff;--line:#999;--accent:#000;--soft:#fff}}
  body{{background:#fff;font-size:12pt}}.wrap{{max-width:none;padding:0}}.noprint{{display:none!important}}
  article{{border:0;padding:0;font-size:12pt}}article h2,article h3{{break-after:avoid}}article table,article blockquote{{break-inside:avoid}}
  article a{{color:#000;text-decoration:none}}@page{{margin:18mm 16mm}}
}}
</style></head><body><div class="wrap">{body}</div></body></html>'''

SITE = 'Театральный фестиваль'

@app.get('/login', response_class=HTMLResponse)
def login_form(next: str = '/', e: int = 0):
    msg = '<div class="err">Неверный пароль</div>' if e else ''
    nxt = html.escape(next if next.startswith('/') and not next.startswith('//') else '/')
    if not PASSWORD:
        return PAGE.format(title='Вход', body=f'<h1>{SITE}</h1><p class="muted">Вход по паролю не настроен. Открой ссылку для входа.</p>')
    return PAGE.format(title='Вход', body=f'''<h1>{SITE}</h1>
<form method="post" action="/login"><label for="pw">Пароль</label>{msg}
<input id="pw" name="password" type="password" autocomplete="current-password" autofocus>
<input type="hidden" name="next" value="{nxt}"><button>Войти</button></form>''')

@app.post('/login')
def login(password: str = Form(''), next: str = Form('/')):
    nxt = next if next.startswith('/') and not next.startswith('//') else '/'
    if PASSWORD and hmac.compare_digest(password, PASSWORD):
        return logged_in(RedirectResponse(nxt, 303))
    return RedirectResponse('/login?e=1&next=' + nxt, 303)

@app.get('/k/{key}')
def login_link(key: str):
    if LINK_KEY and hmac.compare_digest(key, LINK_KEY):
        return logged_in(RedirectResponse('/', 303))
    raise HTTPException(404)

@app.get('/logout')
def logout():
    r = RedirectResponse('/login', 303); r.delete_cookie(COOKIE); return r

@app.get('/healthz')
def healthz(): return {'ok': True}


# ---------- материалы ----------
def check_id(*ids):
    for i in ids:
        if not ID_RE.match(i): raise HTTPException(404)

def find(sec: str, name: str) -> Path | None:
    """Файл раздела: сначала загруженный (DATA), потом из репозитория (CONTENT)."""
    for root in (DATA, CONTENT):
        p = root / sec / name
        if p.is_file(): return p
    return None

def title_of(text: str, default: str):
    m = re.search(r'^#\s+(.+?)\s*#*\s*$', text, re.M)
    return m.group(1) if m else default

def section_title(sec: str):
    p = find(sec, '_title.txt')
    return (p.read_text('utf-8').strip() if p else '') or sec

def all_materials():
    """{раздел: [(id, заголовок, mtime)]}, разделы по свежести, материалы по имени файла."""
    found = {}
    for root in (CONTENT, DATA):  # DATA вторым: перекрывает одноимённые
        if not root.is_dir(): continue
        for p in root.glob('*/*.md'):
            if ID_RE.match(p.parent.name) and ID_RE.match(p.stem):
                found[(p.parent.name, p.stem)] = p
    secs = {}
    for (sec, mid), p in sorted(found.items()):
        secs.setdefault(sec, []).append((mid, title_of(p.read_text('utf-8'), mid), p.stat().st_mtime))
    return dict(sorted(secs.items(), key=lambda kv: -max(t for *_, t in kv[1])))

def fmt_date(ts: float):
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%d.%m.%Y')

@app.get('/', response_class=HTMLResponse)
def index():
    parts = []
    for sec, items in all_materials().items():
        links = ''.join(f'<a class="item" href="/m/{sec}/{mid}"><b>{html.escape(t)}</b>'
                        f'<div class="muted">обновлено {fmt_date(ts)}</div></a>' for mid, t, ts in items)
        parts.append(f'<div class="sec"><h2>{html.escape(section_title(sec))}</h2>{links}</div>')
    body = f'<h1>{SITE}</h1><p class="muted">Подборки текстов и готовые сцены. Любую страницу можно распечатать.</p>' + \
           (''.join(parts) or '<p class="muted">Пока нет ни одного материала.</p>') + \
           '<p class="muted noprint"><a href="/logout" style="color:inherit">Выйти</a></p>'
    return PAGE.format(title=SITE, body=body)

def render(text: str):
    md = markdown.Markdown(extensions=['tables', 'sane_lists', 'toc'],
                           extension_configs={'toc': {'toc_depth': '2-3', 'slugify': toc_slug}})
    return md.convert(text), md.toc_tokens

def toc_slug(value: str, sep: str):
    return re.sub(r'[^\w]+', sep, value.lower(), flags=re.U).strip(sep) or 'h'

def toc_html(tokens):
    def ul(ts):
        return '<ul>' + ''.join(f'<li><a href="#{t["id"]}">{t["name"]}</a>{ul(t["children"]) if t["children"] else ""}</li>'
                                for t in ts) + '</ul>'
    # h1 — заголовок страницы, в оглавление идут его подразделы
    flat = [c for t in tokens for c in (t['children'] if t['level'] == 1 else [t])]
    return f'<nav class="toc noprint"><b>Содержание</b>{ul(flat)}</nav>' if len(flat) > 1 else ''

@app.get('/m/{sec}/{mid}.md')
def material_md(sec: str, mid: str):
    check_id(sec, mid)
    p = find(sec, mid + '.md')
    if not p: raise HTTPException(404)
    return PlainTextResponse(p.read_text('utf-8'), media_type='text/markdown; charset=utf-8')


@app.get('/m/{sec}/{mid}', response_class=HTMLResponse)
def material(sec: str, mid: str):
    check_id(sec, mid)
    p = find(sec, mid + '.md')
    if not p: raise HTTPException(404, 'Нет такого материала')
    text = p.read_text('utf-8')
    body_html, tokens = render(text)
    top = (f'<div class="top noprint"><a href="/">← Все материалы</a>'
           f'<span><a href="/m/{sec}/{mid}.md" download>Скачать .md</a> &nbsp; '
           f'<button class="btn" onclick="print()">Печать</button></span></div>')
    return PAGE.format(title=html.escape(title_of(text, mid)),
                       body=f'{top}<div class="muted noprint">{html.escape(section_title(sec))} · обновлено {fmt_date(p.stat().st_mtime)}</div>'
                            f'{toc_html(tokens)}<article>{body_html}</article>')

# ---------- загрузка (Claude) ----------
def data_path(sec: str, name: str):
    check_id(sec); d = DATA / sec; d.mkdir(parents=True, exist_ok=True); return d / name

@app.get('/api/materials')
def api_list(req: Request):
    need_api(req)
    return {sec: [dict(id=mid, title=t, url=f'/m/{sec}/{mid}') for mid, t, _ in items] for sec, items in all_materials().items()}

@app.put('/api/materials/{sec}/{mid}')
async def api_put(sec: str, mid: str, req: Request):
    """Тело — Markdown (UTF-8). Заменяет загруженную версию, файл из репозитория не трогает."""
    need_api(req); check_id(mid)
    data = await req.body()
    if len(data) > MAX_MD: raise HTTPException(413)
    try: text = data.decode('utf-8')
    except UnicodeDecodeError: raise HTTPException(400, 'Нужен UTF-8')
    p = data_path(sec, mid + '.md'); tmp = p.with_suffix('.tmp'); tmp.write_text(text, 'utf-8'); tmp.replace(p)
    return {'url': f'/m/{sec}/{mid}'}

@app.delete('/api/materials/{sec}/{mid}')
def api_delete(sec: str, mid: str, req: Request):
    need_api(req); check_id(sec, mid)
    p = DATA / sec / (mid + '.md')
    if not p.exists(): raise HTTPException(404, 'Загруженной версии нет')
    p.unlink(); return {'ok': True}

@app.put('/api/sections/{sec}/title')
async def api_section_title(sec: str, req: Request):
    need_api(req)
    t = (await req.body()).decode('utf-8', 'replace').strip()[:200]
    data_path(sec, '_title.txt').write_text(t + '\n', 'utf-8')
    return {'ok': True}
