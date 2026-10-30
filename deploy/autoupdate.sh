#!/bin/sh
# Автообновление сайта из GitHub: deploy/autoupdate.sh <папка репо> "<команда перезапуска>"
# Если в GitHub появились новые коммиты — подтягивает их. Если поменялся код (не только content/ и .md) —
# выполняет команду перезапуска. Запускается таймером раз в 5 минут (teatr-update.timer).
set -e
cd "$1"
dir="$1"; g() { git -c safe.directory="$dir" "$@"; }
g fetch --quiet origin
old=$(g rev-parse HEAD); new=$(g rev-parse '@{u}')
[ "$old" = "$new" ] && exit 0
g merge --ff-only --quiet '@{u}'
echo "обновлено ${old%"${old#???????}"} → ${new%"${new#???????}"}"
if g diff --name-only "$old" "$new" | grep -qvE '^content/|\.md$'; then
    echo "поменялся код, перезапуск: $2"
    sh -c "$2"
fi
