const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("kedr", {
  platform: process.platform,
  pick(kind, locale) {
    return ipcRenderer.invoke("kedr:pick", kind, locale);
  },
  reveal(folder) {
    return ipcRenderer.invoke("kedr:reveal", folder);
  },
});
