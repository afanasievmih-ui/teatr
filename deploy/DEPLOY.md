# Деплой на сервер (Hetzner) — teatr.idealcontinent.org

Всё как у proverka.idealcontinent.org: тот же сервер, тот же nginx, свой поддомен и порт 8091.
Сервер сам проверяет GitHub раз в 5 минут: новые материалы (`content/`) появляются сразу,
при изменении кода сайт перезапускается сам. Публикация = коммит и push, на сервер заходить не нужно.

## 1. DNS

В панели домена idealcontinent.org добавить запись (как для `proverka`):

| Тип | Имя | Значение | TTL |
|---|---|---|---|
| A | `teatr` | IPv4 сервера (тот же, что у `idealcontinent.org`) | 300 |
| AAAA | `teatr` | IPv6 сервера, если у основного домена тоже есть AAAA | 300 |

Если домен за Cloudflare: сначала «DNS only» (серое облако), чтобы certbot получил сертификат.
Проверка: `dig +short teatr.idealcontinent.org` показывает IP сервера.

## 2. Код и секреты

```bash
sudo mkdir -p /opt/teatr && cd /opt/teatr
sudo git clone -b claude/project-thread-bs93sf https://github.com/afanasievmih-ui/teatr.git .   # репо публичный, токен не нужен
cp .env.example .env
python3 - <<'PY'   # сгенерировать секреты в .env
import secrets, re
s = open('.env').read()
for k in ['TEATR_API_TOKEN', 'TEATR_SECRET']:
    s = re.sub(rf'^{k}=.*$', f'{k}={secrets.token_urlsafe(24)}', s, flags=re.M)
open('.env', 'w').write(s)
PY
# по умолчанию сайт открыт без пароля; закрыть: вписать TEATR_PASSWORD в .env
chmod 600 .env
```

Если позже основной веткой станет `main`: `git checkout main` в `/opt/teatr`.

## 3. Запуск

**Вариант A — Docker:**

```bash
docker compose up -d --build
curl -s localhost:8091/healthz      # {"ok":true}
```

**Вариант B — без Docker (systemd):**

```bash
sudo useradd -r -s /usr/sbin/nologin teatr
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo chown -R teatr /opt/teatr
sudo cp deploy/teatr.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now teatr
curl -s localhost:8091/healthz
```

**Автообновление из GitHub (оба варианта):**

```bash
sudo cp deploy/teatr-update.service deploy/teatr-update.timer /etc/systemd/system/
# без Docker: в teatr-update.service заменить команду перезапуска на "systemctl restart teatr"
sudo systemctl daemon-reload && sudo systemctl enable --now teatr-update.timer
sudo systemctl start teatr-update.service && journalctl -u teatr-update -n 5   # проверка
```

Тот же `autoupdate.sh` подходит для любого сайта (например, proverka): скопировать пару service/timer,
поменять папку и команду перезапуска. Для приватного репозитория на сервере нужен deploy key.

## 4. nginx + HTTPS

```bash
sudo cp deploy/nginx-teatr.conf /etc/nginx/sites-available/teatr
sudo ln -s /etc/nginx/sites-available/teatr /etc/nginx/sites-enabled/teatr
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d teatr.idealcontinent.org
```

## 5. Проверка

- https://teatr.idealcontinent.org → сразу оглавление.
- Если понадобится закрыть сайт: вписать в `.env` `TEATR_PASSWORD` (вход по паролю) и/или `TEATR_LINK_KEY`
  (вход по ссылке `/k/<ключ>`, кука на год) и перезапустить.

Данные, загруженные через API, лежат в `/opt/teatr/data`, git их не трогает.
