Pathfinder Spellbook for Telegram.

Available at [@SpellsBot](https://t.me/SpellsBot).

### Run
Build
```
docker build --rm -t spellsbot .
```

Run the container providing `--env-file` and `-v` mounts for database file and table data directory
```
docker run -d --name spellsbot-dev \
  --env-file .env.dev \
  -v /botdata/db_files:/db_data \
  -v /botdata/data:/table_data \
  spellsbot

```

### Telegram Commands
`/start` - Приветствие

`/menu` - Поиск по классам и кругам

`/spellbook` - Моя книга заклинаний

`/help` - Как пользоваться книгой

`/settings` - Настройки поиска
