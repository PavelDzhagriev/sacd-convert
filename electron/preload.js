const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("kedr", {
  platform: process.platform,
  pick(kind) {
    return ipcRenderer.invoke("kedr:pick", kind);
  },
  reveal(folder) {
    return ipcRenderer.invoke("kedr:reveal", folder);
  },
});
