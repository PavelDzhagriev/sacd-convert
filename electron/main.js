const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require("electron");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

app.setName("Кедр");

let engine = null;
let mainWindow = null;

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function systemLocale() {
  const tag = String(app.getLocale() || "").toLowerCase();
  return tag === "ru" || tag.startsWith("ru-") ? "ru" : "en";
}

function engineText() {
  if (systemLocale() === "ru") {
    return {
      timeout: "Движок Кедра не ответил за 20 секунд.",
      stopped: (code, tail) => `Движок Кедра остановился (код ${code}).${tail ? `\n${tail}` : ""}`,
      python: (message) => `Не удалось запустить Python: ${message}`,
    };
  }
  return {
    timeout: "The Kedr engine did not respond within 20 seconds.",
    stopped: (code, tail) => `The Kedr engine stopped (code ${code}).${tail ? `\n${tail}` : ""}`,
    python: (message) => `Could not start Python: ${message}`,
  };
}

function dialogCopy(locale) {
  if (locale === "ru") {
    return {
      fileTitle: "Образ SACD или DSF",
      filter: "SACD и DSD",
      all: "Все файлы",
      folderTitle: "Папка для альбомов",
    };
  }
  return {
    fileTitle: "SACD image or DSF",
    filter: "SACD and DSD",
    all: "All files",
    folderTitle: "Album folder",
  };
}

function waitForEngine(child, port) {
  const text = engineText();
  return new Promise((resolve, reject) => {
    let buffer = "";
    const timer = setTimeout(() => {
      reject(new Error(text.timeout));
    }, 20000);
    const finish = (error) => {
      clearTimeout(timer);
      child.stdout.off("data", onData);
      child.stderr.off("data", onData);
      child.off("exit", onExit);
      if (error) reject(error);
      else resolve();
    };
    const onData = (chunk) => {
      buffer += chunk.toString();
      if (buffer.includes(`http://127.0.0.1:${port}`)) finish();
    };
    const onExit = (code) => {
      const tail = buffer.trim().split("\n").slice(-8).join("\n");
      finish(new Error(text.stopped(code, tail)));
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", onData);
    child.on("exit", onExit);
  });
}

function pythonLaunch() {
  if (process.platform !== "win32") return { command: "python3", prefix: [] };
  const options = [
    ["py", ["-3"]],
    ["python", []],
    ["python3", []],
  ];
  for (const [command, prefix] of options) {
    const probe = spawnSync(command, [...prefix, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"], {
      windowsHide: true,
      timeout: 8000,
    });
    if (probe.status === 0) return { command, prefix };
  }
  return { command: "py", prefix: ["-3"] };
}

async function startEngine() {
  const port = await freePort();
  const env = { ...process.env, PYTHONPATH: ROOT, PYTHONUNBUFFERED: "1" };
  if (process.platform === "darwin") {
    env.PATH = ["/opt/homebrew/bin", "/usr/local/bin", env.PATH || ""].filter(Boolean).join(":");
  }
  if (process.platform === "win32") {
    env.PYTHONUTF8 = "1";
    env.PYTHONIOENCODING = "utf-8";
    const extractor = path.join(ROOT, "bin", "sacd_extract.exe");
    if (!env.KEDR_SACD_EXTRACT && fs.existsSync(extractor)) env.KEDR_SACD_EXTRACT = extractor;
  }
  const python = pythonLaunch();
  const child = spawn(python.command, [...python.prefix, "-m", "kedr", "serve", "--port", String(port)], {
    cwd: ROOT,
    env,
    detached: process.platform !== "win32",
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  engine = child;
  child.on("error", (error) => {
    dialog.showErrorBox("Кедр", engineText().python(error.message));
  });
  await waitForEngine(child, port);
  return port;
}

function stopEngine() {
  if (!engine || engine.killed) return;
  const pid = engine.pid;
  engine = null;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/F", "/T", "/PID", String(pid)], { windowsHide: true });
    return;
  }
  try {
    process.kill(-pid, "SIGTERM");
  } catch (_error) {
    try {
      process.kill(pid, "SIGTERM");
    } catch (_again) {
      /* процесс уже завершился */
    }
  }
}

function createWindow(port) {
  const darwin = process.platform === "darwin";
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 860,
    minWidth: 760,
    minHeight: 640,
    backgroundColor: "#14110e",
    title: "Кедр",
    icon: path.join(ROOT, "kedr", "web", "icon.png"),
    titleBarStyle: darwin ? "hiddenInset" : "default",
    trafficLightPosition: darwin ? { x: 16, y: 18 } : undefined,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadURL(`http://127.0.0.1:${port}/`);
}

function buildMenu() {
  const template = [];
  if (process.platform === "darwin") template.push({ role: "appMenu" });
  template.push({ role: "fileMenu" }, { role: "editMenu" }, { role: "viewMenu" }, { role: "windowMenu" });
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

ipcMain.handle("kedr:pick", async (_event, kind, locale) => {
  const parent = BrowserWindow.getFocusedWindow() || mainWindow;
  const file = kind === "iso" || kind === "file";
  const copy = dialogCopy(locale === "ru" ? "ru" : locale === "en" ? "en" : systemLocale());
  const result = await dialog.showOpenDialog(parent, file
    ? {
      title: copy.fileTitle,
      properties: ["openFile"],
      filters: [
        { name: copy.filter, extensions: ["iso", "dsf", "dff"] },
        { name: copy.all, extensions: ["*"] },
      ],
    }
    : {
      title: copy.folderTitle,
      properties: ["openDirectory", "createDirectory"],
    });
  if (result.canceled || !result.filePaths[0]) return { cancelled: true };
  return { path: result.filePaths[0] };
});

ipcMain.handle("kedr:reveal", async (_event, folder) => {
  const error = await shell.openPath(String(folder || ""));
  if (error) throw new Error(error);
  return { ok: true };
});

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });

  app.whenReady().then(async () => {
    buildMenu();
    try {
      const port = await startEngine();
      createWindow(port);
    } catch (error) {
      dialog.showErrorBox("Кедр", error && error.message ? error.message : String(error));
      app.quit();
    }
  });
}

app.on("window-all-closed", () => {
  stopEngine();
  app.quit();
});

app.on("before-quit", () => {
  stopEngine();
});
