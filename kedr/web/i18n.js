(function () {
  const TEXT = {
    ru: {
      title: "Кедр — SACD в FLAC или MP3",
      eyebrow: "Утилита для macOS",
      eyebrowDesktop: "Настольное приложение",
      healthChecking: "Проверяю инструменты…",
      healthUnreachable: "Не удалось спросить инструменты",
      healthReadySoxr: "ffmpeg с SoX и sacd_extract на месте",
      healthReady: "ffmpeg и sacd_extract на месте",
      healthMissing: "Нет {tools}. {hint}",
      hintMac: "Выполните scripts/install-macos.sh — скрипт поставит ffmpeg и соберёт sacd_extract.",
      hintOther: "Соберите extractor скриптом scripts/build-sacd-extract.sh и поставьте ffmpeg.",
      isoPlaceholder: "SACD ISO или DSF",
      filePath: "Путь к файлу",
      pickFile: "Файл",
      readDisc: "Прочитать",
      toc: "Оглавление",
      discEmptyTitle: "Диск ещё не прочитан",
      discEmptyCopy: "Выберите образ или уже извлечённый DSF.",
      untitled: "Без названия",
      unknownArtist: "Исполнитель не указан",
      tracksTitle: "Дорожки",
      tracksPending: "Появятся после чтения диска.",
      selectAll: "Все",
      reveal: "Открыть папку",
      leadFlac: "176,4 кГц и срез 40 кГц для DSD64.",
      leadMp3: "LAME, не выше 48 кГц.",
      format: "Формат",
      sampleRate: "Частота",
      bitDepth: "Разрядность",
      bitrate: "Битрейт, кбит/с",
      lowpass: "Срез шума",
      compression: "Сжатие FLAC",
      saveTo: "Куда сохранить",
      folderPath: "Папка для альбомов",
      pickFolder: "Папка",
      convert: "Преобразовать в {format}",
      cancel: "Остановить",
      mp3Blocked: "MP3 не вмещает 5.1. Выберите FLAC или стереозону.",
      noLame: "В ffmpeg нет LAME, MP3 записать не получится.",
      requestFailed: "Запрос не прошёл",
      needPath: "Вставьте путь к SACD ISO или DSF.",
      doneLine: "Готово, {files}. {dir}",
      stopped: "Остановлено. Уже записанные файлы остались в папке.",
      tracksMeta: "{label} · {count} дор. · {time}",
      estimateMp3: "Около {size} на {count} дор. Постоянный битрейт {bitrate} кбит/с.",
      estimateFlac: "Около {size} на {count} дор. Оценка до сжатия FLAC, с запасом.",
      fileOne: "{count} файл",
      fileFew: "{count} файла",
      fileMany: "{count} файлов",
      khz: "кГц",
      off: "Выкл",
      bits: "{n} бит",
      kb: "КБ",
      mb: "МБ",
      gb: "ГБ",
      statusPending: "Ждёт",
      statusExtracting: "Извлечение",
      statusEncoding: "Запись",
      statusDone: "Готово",
      statusError: "Ошибка",
      stereo: "Стерео",
      multichannel: "Многоканальный",
      channelCount: "{n} кан.",
      language: "Язык",
      andWord: "и",
    },
    en: {
      title: "Kedr — SACD to FLAC or MP3",
      eyebrow: "macOS utility",
      eyebrowDesktop: "Desktop app",
      healthChecking: "Checking tools…",
      healthUnreachable: "Could not reach the tools",
      healthReadySoxr: "ffmpeg with SoX and sacd_extract are ready",
      healthReady: "ffmpeg and sacd_extract are ready",
      healthMissing: "Missing {tools}. {hint}",
      hintMac: "Run scripts/install-macos.sh to install ffmpeg and build sacd_extract.",
      hintOther: "Build the extractor with scripts/build-sacd-extract.sh and install ffmpeg.",
      isoPlaceholder: "SACD ISO or DSF",
      filePath: "File path",
      pickFile: "File",
      readDisc: "Read",
      toc: "Contents",
      discEmptyTitle: "No disc yet",
      discEmptyCopy: "Choose an image or an extracted DSF.",
      untitled: "Untitled",
      unknownArtist: "Artist unknown",
      tracksTitle: "Tracks",
      tracksPending: "They appear after the disc is read.",
      selectAll: "All",
      reveal: "Show folder",
      leadFlac: "176.4 kHz and a 40 kHz lowpass for DSD64.",
      leadMp3: "LAME, no higher than 48 kHz.",
      format: "Format",
      sampleRate: "Sample rate",
      bitDepth: "Bit depth",
      bitrate: "Bitrate, kbps",
      lowpass: "Lowpass",
      compression: "FLAC compression",
      saveTo: "Save to",
      folderPath: "Album folder",
      pickFolder: "Folder",
      convert: "Convert to {format}",
      cancel: "Stop",
      mp3Blocked: "MP3 cannot hold 5.1. Choose FLAC or the stereo area.",
      noLame: "This ffmpeg has no LAME, so MP3 cannot be written.",
      requestFailed: "The request failed",
      needPath: "Enter a path to a SACD ISO or a DSF.",
      doneLine: "Done, {files}. {dir}",
      stopped: "Stopped. Files already written remain in the folder.",
      tracksMeta: "{label} · {count} tracks · {time}",
      estimateMp3: "About {size} for {count} tracks. Constant bitrate {bitrate} kbps.",
      estimateFlac: "About {size} for {count} tracks. A rough size before FLAC compression.",
      fileOne: "{count} file",
      fileFew: "{count} files",
      fileMany: "{count} files",
      khz: "kHz",
      off: "Off",
      bits: "{n}-bit",
      kb: "KB",
      mb: "MB",
      gb: "GB",
      statusPending: "Waiting",
      statusExtracting: "Extracting",
      statusEncoding: "Writing",
      statusDone: "Done",
      statusError: "Error",
      stereo: "Stereo",
      multichannel: "Multichannel",
      channelCount: "{n} ch",
      language: "Language",
      andWord: "and",
    },
  };

  const SERVER = {
    "Не выбрано ни одной дорожки.": "No tracks selected.",
    "MP3 хранит только моно и стерео. Для многоканальной зоны выберите FLAC.": "MP3 holds only mono and stereo. Choose FLAC for the multichannel area.",
    "В ffmpeg нет кодировщика LAME. На Mac: brew reinstall ffmpeg.": "This ffmpeg has no LAME encoder. On a Mac: brew reinstall ffmpeg.",
    "Укажите папку, куда сохранить файлы.": "Choose a folder for the files.",
    "Папка назначения оказалась файлом.": "The destination is a file, not a folder.",
    "sacd_extract не создал DSF.": "sacd_extract did not create a DSF.",
    "Читаю образ": "Reading the disc",
    "Готово": "Done",
    "Остановлено": "Stopped",
    "DSD-файл уже извлечён": "The DSD file is already extracted",
    "Извлекаю DSD из образа": "Extracting DSD from the image",
    "На этом диске нет стереофонической зоны.": "This disc has no stereo area.",
    "На этом диске нет многоканальной зоны.": "This disc has no multichannel area.",
    "Формат: FLAC или MP3.": "Format must be FLAC or MP3.",
    "Для FLAC частота: 88,2, 176,4 или 352,8 кГц.": "FLAC sample rate must be 88.2, 176.4, or 352.8 kHz.",
    "Разрядность FLAC: 16 или 24 бита.": "FLAC bit depth must be 16 or 24.",
    "Сжатие FLAC — от 0 до 8.": "FLAC compression must be from 0 to 8.",
    "Для MP3 частота 44,1 или 48 кГц. Выше MPEG не хранит.": "MP3 sample rate must be 44.1 or 48 kHz. MPEG does not store anything higher.",
    "Битрейт MP3: 128, 192, 256 или 320 кбит/с.": "MP3 bitrate must be 128, 192, 256, or 320 kbps.",
    "Частота среза должна быть от 0 до 80 кГц.": "The lowpass must be from 0 to 80 kHz.",
    "Срез выше частоты Найквиста для выбранной дискретизации. Уменьшите срез или поднимите частоту.": "The lowpass is above the Nyquist frequency for this sample rate. Lower the lowpass or raise the rate.",
    "Не найден ffmpeg. На Mac: brew install ffmpeg. Без него DSD не во что переводить: FLAC хранит PCM.": "ffmpeg was not found. On a Mac: brew install ffmpeg. DSD has to become PCM before it can be stored as FLAC.",
    "Не найден ffprobe. Он ставится вместе с ffmpeg.": "ffprobe was not found. It is installed together with ffmpeg.",
    "Не найден sacd_extract. На Mac выполните scripts/install-macos.sh — скрипт соберёт его из sacd-ripper. Обычный ffmpeg образ SACD не читает.": "sacd_extract was not found. On a Mac, run scripts/install-macos.sh. It builds the tool from sacd-ripper. Ordinary ffmpeg cannot read a SACD image.",
    "Укажите путь к SACD ISO или DSF.": "Enter a path to a SACD ISO or a DSF.",
    "Нужен файл, а не папка.": "A file is required, not a folder.",
    "Нужен образ SACD (.iso) или файл DSD (.dsf).": "A SACD image (.iso) or a DSD file (.dsf) is required.",
    "Не удалось прочитать образ. Файл не похож на SACD ISO или sacd_extract не смог его открыть.": "Could not read the image. It does not look like a SACD ISO, or sacd_extract could not open it.",
    "ffprobe слишком долго читал файл.": "ffprobe took too long to read the file.",
    "ffmpeg не смог прочитать этот DSD-файл.": "ffmpeg could not read this DSD file.",
    "ffmpeg вернул непонятный ответ.": "ffmpeg returned a response that could not be read.",
    "В файле нет звуковой дорожки.": "The file has no audio track.",
    "Файл не похож на SACD ISO. Кедр читает образы Super Audio CD, не обычные CD, DVD или Blu-ray ISO.": "This file does not look like a SACD ISO. Kedr reads Super Audio CD images, not ordinary CD, DVD, or Blu-ray ISOs.",
    "sacd_extract не смог вывести текст в UTF-8. Нужна локаль UTF-8.": "sacd_extract could not print text as UTF-8. A UTF-8 locale is required.",
    "В выводе sacd_extract нет дорожек. Проверьте, что это полный образ SACD ISO.": "sacd_extract printed no tracks. Check that this is a complete SACD ISO.",
    "Слишком большой запрос.": "The request is too large.",
    "Не удалось разобрать запрос.": "The request could not be read.",
    "Список дорожек должен быть массивом номеров.": "The track list must be an array of numbers.",
    "Номера дорожек начинаются с 1.": "Track numbers start at 1.",
    "Неизвестный диалог.": "Unknown dialog.",
    "Окно выбора файла доступно в приложении на Mac. Вставьте путь вручную.": "The file dialog is available in the Mac app. Paste the path instead.",
    "Этой папки уже нет.": "That folder is no longer there.",
    "Открыть папку из этой среды нельзя. Путь есть в строке результата.": "This environment cannot open the folder. The path is in the result line.",
    "Нет такой страницы.": "No such page.",
    "Задача не найдена.": "The job was not found.",
    "Проверьте числа в настройках.": "Check the numbers in the settings.",
    "Нет такого запроса.": "No such request.",
    "Файл интерфейса не найден.": "The interface file was not found.",
  };

  const PATTERNS = [
    [/^Файл не найден: ([\s\S]+)$/, (match) => `File not found: ${match[1]}`],
    [/^На диске нет дорожек: (.+)\.$/, (match) => `These tracks are not on the disc: ${match[1]}.`],
    [/^Не нашёл DSF для дорожек (.+)\. В папке: (.+)\.$/, (match) => `No DSF for tracks ${match[1]}. In the folder: ${match[2]}.`],
    [/^Дорожка (\d+): ([\s\S]+)$/, (match) => `Track ${match[1]}: ${match[2]}`],
    [/^Не удалось запустить (.+): ([\s\S]+)$/, (match) => `Could not start ${match[1]}: ${match[2]}`],
    [/^Сбой преобразования: ([\s\S]+)$/, (match) => `Conversion failed: ${match[1]}`],
    [/^Пишу (FLAC|MP3)$/, (match) => `Writing ${match[1]}`],
    [/^sacd_extract завершился с кодом (\d+)\.$/, (match) => `sacd_extract exited with code ${match[1]}.`],
  ];

  function negotiate(saved, tags) {
    if (saved === "ru" || saved === "en") return saved;
    const list = tags && tags.length ? tags : [];
    for (const tag of list) {
      const base = String(tag || "").toLowerCase().replace("_", "-").split("-")[0];
      if (base === "ru" || base === "en") return base;
    }
    return "en";
  }

  function fill(template, vars) {
    let text = template;
    if (!vars) return text;
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
    return text;
  }

  function mount(locale) {
    const lang = locale === "ru" ? "ru" : "en";

    function t(key, vars) {
      const template = TEXT[lang][key] ?? TEXT.en[key] ?? key;
      return fill(template, vars);
    }

    function serverText(text) {
      if (!text || lang === "ru") return text || "";
      if (SERVER[text]) return SERVER[text];
      for (const [pattern, render] of PATTERNS) {
        const match = pattern.exec(text);
        if (match) return render(match);
      }
      return text;
    }

    function formatHz(value) {
      const khz = value / 1000;
      const raw = Number.isInteger(khz) ? String(khz) : khz.toFixed(1);
      const shown = lang === "ru" ? raw.replace(".", ",") : raw;
      return `${shown} ${t("khz")}`;
    }

    function formatBytes(size) {
      const gb = size >= 1024 ** 3;
      const mb = size >= 1024 ** 2;
      const value = gb ? size / 1024 ** 3 : mb ? size / 1024 ** 2 : size / 1024;
      const digits = gb ? value.toFixed(1) : String(Math.round(value));
      const shown = lang === "ru" ? digits.replace(".", ",") : digits;
      return `${shown} ${t(gb ? "gb" : mb ? "mb" : "kb")}`;
    }

    function filesLabel(count) {
      if (lang !== "ru") return t(count === 1 ? "fileOne" : "fileMany", { count });
      const mod100 = Math.abs(count) % 100;
      const mod10 = mod100 % 10;
      if (mod100 > 10 && mod100 < 20) return t("fileMany", { count });
      if (mod10 === 1) return t("fileOne", { count });
      if (mod10 >= 2 && mod10 <= 4) return t("fileFew", { count });
      return t("fileMany", { count });
    }

    function areaLabel(area) {
      if (!area) return "";
      if (area.label === "Стерео") return t("stereo");
      if (area.label === "Многоканальный") return t("multichannel");
      const channels = /^(\d+) кан\.$/.exec(area.label || "");
      if (channels) return t("channelCount", { n: channels[1] });
      return area.label || "";
    }

    function status(code) {
      const keys = {
        pending: "statusPending",
        extracting: "statusExtracting",
        encoding: "statusEncoding",
        done: "statusDone",
        error: "statusError",
      };
      return keys[code] ? t(keys[code]) : (code || "");
    }

    function joinAnd(items) {
      const word = t("andWord");
      if (items.length <= 1) return items[0] || "";
      if (items.length === 2) return `${items[0]} ${word} ${items[1]}`;
      return `${items.slice(0, -1).join(", ")} ${word} ${items[items.length - 1]}`;
    }

    return { locale: lang, t, serverText, formatHz, formatBytes, filesLabel, areaLabel, status, joinAnd };
  }

  function savedLocale() {
    try {
      const saved = JSON.parse(localStorage.getItem("kedr-settings") || "{}");
      return saved.locale;
    } catch (_error) {
      return null;
    }
  }

  const api = { TEXT, negotiate, mount, savedLocale };
  if (typeof window !== "undefined") window.KedrI18n = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;

  if (typeof document !== "undefined" && typeof navigator !== "undefined" && typeof localStorage !== "undefined") {
    const tags = navigator.languages && navigator.languages.length
      ? navigator.languages
      : [navigator.language];
    document.documentElement.lang = negotiate(savedLocale(), tags);
  }
})();
