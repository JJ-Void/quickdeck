# Как выложить на GitHub

## 1. Создать репозиторий

На github.com → New repository → имя `quickdeck`, публичный, **без** README,
.gitignore и лицензии — они уже есть в проекте.

## 2. Залить код

В папке проекта, в командной строке:

```bat
git init
git add .
git commit -m "QuickDeck 1.0.0"
git branch -M main
git remote add origin https://github.com/ВАШ_ЛОГИН/quickdeck.git
git push -u origin main
```

Если git не установлен — `winget install Git.Git`, потом закрыть и открыть окно консоли.

При первом push попросит войти — откроется окно браузера, это нормально.

## 3. Заменить OWNER на свой логин

В `README.md` и `installer/quickdeck.iss` в ссылках стоит `OWNER`. Заменить на логин:

```bat
powershell -Command "(Get-Content README.md) -replace 'OWNER','ВАШ_ЛОГИН' | Set-Content README.md"
powershell -Command "(Get-Content installer\quickdeck.iss) -replace 'OWNER','ВАШ_ЛОГИН' | Set-Content installer\quickdeck.iss"
git commit -am "ссылки на репозиторий"
git push
```

## 4. Выпустить релиз

```bat
git tag v1.0.0
git push origin v1.0.0
```

Дальше всё делает GitHub: на своей Windows-машине собирает программу, установщик
и портативный архив, создаёт релиз и прикладывает файлы. Идёт около пяти минут,
следить можно во вкладке Actions. Ссылку на релиз и раздаёшь.

Настройка сборки — `.github/workflows/build.yml`. Собирать у себя больше не нужно:
меняешь код, ставишь новый тег — GitHub выдаёт готовые файлы.

## 5. Оформить страницу

- **About** справа: короткое описание и тема. Теги: `windows`, `launcher`, `productivity`,
  `python`, `pyside6`, `radial-menu`, `quick-access`.
- **Releases** → закрепить последний.
- Добавить гифку в начало README: 10–15 секунд, как Alt + колесо открывает папку.
  Записать можно ShareX или ScreenToGif, положить в `docs/demo.gif`.

## Что дальше по версиям

Правишь код → `git commit` → `git push` → новый тег `v1.0.1` → релиз собирается сам.
Историю изменений вести в `CHANGELOG.md`, GitHub подтянет её в описание релиза.
