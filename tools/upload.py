"""Выложить материалы на сайт через API (когда сервер доступен из сессии Claude).

python3 tools/upload.py content/<раздел>/<материал>.md [ещё файлы…]

Раздел — имя папки, материал — имя файла без .md (латиница, цифры, - и _).
Файл _title.txt в папке задаёт название раздела.
Адрес и токен: переменные TEATR_URL (например https://teatr.idealcontinent.org) и TEATR_API_TOKEN.
Обычный путь публикации — коммит в content/ (сервер сам делает git pull), API нужен, если текст нельзя класть в репозиторий.
"""
import os, sys, urllib.request
from pathlib import Path

def main():
    files = [Path(a) for a in sys.argv[1:]]
    if not files: sys.exit(__doc__)
    url, token = os.environ.get('TEATR_URL', '').rstrip('/'), os.environ.get('TEATR_API_TOKEN', '')
    if not url or not token: sys.exit('Нужны TEATR_URL и TEATR_API_TOKEN')
    for f in files:
        sec = f.parent.name
        path = f'/api/sections/{sec}/title' if f.name == '_title.txt' else f'/api/materials/{sec}/{f.stem}'
        req = urllib.request.Request(url + path, f.read_bytes(), method='PUT', headers={
            'Authorization': 'Bearer ' + token, 'Content-Type': 'text/markdown; charset=utf-8'})
        try:
            urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            sys.exit(f'{f}: ошибка {e.code}: {e.read().decode()}')
        print(url + (f'/m/{sec}/{f.stem}' if f.suffix == '.md' else '/'))

if __name__ == '__main__':
    main()
