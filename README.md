# Кедр

Настольная утилита: SACD ISO (DSD) и файлы DSF → PCM FLAC или MP3.

Образ Super Audio CD хранит однобитный DSD, часто ещё и сжатый в DST. Ни FLAC, ни MP3 так не умеют: оба хранят PCM. Кедр читает оглавление, снимает DST и пишет выбранный формат с тегами из диска. Окно — Electron, преобразование делает локальный Python.

## Что нужно

- macOS 11 или новее, либо Windows 10/11 (на Linux работает окно Electron и команда `python3 -m kedr`)
- На Mac — [Homebrew](https://brew.sh). На Windows — winget, он уже есть в системе
- Python 3.9+, Node.js, ffmpeg и `sacd_extract`

`sacd_extract` — отдельная программа из [sacd-ripper](https://github.com/sacd-ripper/sacd-ripper) (GPL-2.0). Обычный ffmpeg образ SACD не открывает. Код Кедра — MIT, extractor при установке скачивается и собирается отдельно.

## Установка на Mac

Из папки с этим файлом:

```bash
./scripts/install-macos.sh
open ~/Applications/Kedr.app
```

Скрипт ставит `cmake`, `pkgconf`, `libxml2`, `ffmpeg`, Python и Node, собирает `sacd_extract`, ставит Electron и кладёт ярлык «Кедр» в `~/Applications`. `libxml2` в Homebrew спрятана от системных заголовков, скрипт сам подставляет её путь. Окно открывает локальную страницу. В интернет альбом не уходит.

Повторный запуск скрипта обновляет ярлык после изменений в этой папке.

## Установка на Windows

В PowerShell, из папки с этим файлом. Для MSYS2 в `C:\msys64` обычно нужны права администратора:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1
```

Скрипт через winget ставит MSYS2, Python, Node и ffmpeg, в UCRT64 собирает `sacd_extract.exe` (DLL ложатся рядом с ним), ставит Electron и кладёт ярлык «Кедр» на рабочий стол. Ярлык — `dist\Kedr.cmd`: он запускает Electron из этой папки. Подписанного установщика нет, собирать нужно на самой Windows.

Папку проекта после установки не переносите: ярлык указывает на неё.

Без установщика, из этой же папки:

```bash
npm install
npm start
```

Тот же интерфейс в браузере, без Electron:

```bash
python3 -m kedr serve --open
```

## Как пользоваться

1. «Выбрать файл» или вставьте путь к `.iso` / `.dsf`.
2. «Прочитать» — появятся исполнитель, альбом и дорожки. Если на диске есть стерео и 5.1, выберите зону.
3. Выберите FLAC или MP3.
4. Укажите папку. Внутри неё появится каталог `Исполнитель — Альбом`.
5. «Преобразовать в FLAC» или «Преобразовать в MP3».

FLAC по умолчанию: 176,4 кГц, 24 бит, срез шума 40 кГц, сжатие 8. Срез убирает ультразвуковой шум DSD. 352,8 кГц — без дополнительного понижения частоты, файлы заметно больше.

MP3 по умолчанию: LAME, 320 кбит/с, 44,1 кГц, срез 20 кГц. MPEG не хранит частоту выше 48 кГц и не хранит 5.1 — для многоканальной зоны остаётся FLAC.

Промежуточные DSF удаляются. Если остановить задачу, уже записанные файлы остаются.

## Командная строка

```bash
python3 -m kedr serve --open
python3 -m kedr info "/path/Album.iso"
python3 -m kedr convert "/path/Album.iso" -o ~/Music --mode stereo --rate 176400
python3 -m kedr convert "/path/Album.iso" -o ~/Music --format mp3 --bitrate 320
python3 -m kedr convert "/path/Album.iso" -o ~/Music --mode multi --tracks 1,2,4
python3 -m kedr tools
```

`--mode multi` — многоканальная зона, если она есть на диске. Для MP3 она отклоняется: у MP3 только моно и стерео.

`npm start` открывает настольное окно. `python3 -m kedr` без команды поднимает ту же страницу в браузере.

## Проверка

```bash
python3 -m unittest discover -s tests
```

Тесты гоняют синтетический тон 440 Гц в FLAC и MP3. Полный SACD ISO в репозиторий не входит: это чужие записи.

## Ограничения

- Результат — PCM, не «бит-в-бит» DSD. Иначе это был бы DSF.
- Нужен целый образ SACD, не DVD-Audio и не обычный CD ISO.
- MP3 не бывает многоканальным и не бывает выше 48 кГц. Для 5.1 нужен FLAC.
- Многоканальный FLAC воспроизводят не все плееры.
- Подписанного приложения с вложенным Electron здесь нет. На Mac `scripts/install-macos.sh` и на Windows `scripts/install-windows.ps1` ставят Electron в папку проекта и запускают его из ярлыка.
