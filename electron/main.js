const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
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

function waitForEngine(child, port) {
  return new Promise((resolve, reject) => {
    let buffer = "";
    const timer = setTimeout(() => {
      reject(new Error("Движок Кедра не ответил за 20 секунд."));
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
      finish(new Error(`Движок Кедра остановился (код ${code}).${tail ? `\n${tail}` : ""}`));
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", onData);
    child.on("exit", onExit);
  });
}

async function startEngine() {
  const port = await freePort();
  const env = { ...process.env, PYTHONPATH: ROOT, PYTHONUNBUFFERED: "1" };
  if (process.platform === "darwin") {
    env.PATH = ["/opt/homebrew/bin", "/usr/local/bin", env.PATH || ""].filter(Boolean).join(":");
  }
  const child = spawn("python3", ["-m", "kedr", "serve", "--port", String(port)], {
    cwd: ROOT,
    env,
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
  });
  engine = child;
  child.on("error", (error) => {
    dialog.showErrorBox("Кедр", `Не удалось запустить Python: ${error.message}`);
  });
  await waitForEngine(child, port);
  return port;
}

function stopEngine() {
  if (!engine || engine.killed) return;
  const pid = engine.pid;
  engine = null;
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

ipcMain.handle("kedr:pick", async (_event, kind) => {
  const parent = BrowserWindow.getFocusedWindow() || mainWindow;
  const file = kind === "iso" || kind === "file";
  const result = await dialog.showOpenDialog(parent, file
    ? {
      title: "Образ SACD или DSF",
      properties: ["openFile"],
      filters: [
        { name: "SACD и DSD", extensions: ["iso", "dsf", "dff"] },
        { name: "Все файлы", extensions: ["*"] },
      ],
    }
    : {
      title: "Папка для альбомов",
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
