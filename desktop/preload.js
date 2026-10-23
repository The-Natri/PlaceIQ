// The loading screen's only bridge to the main process: it receives status
// messages and can ask for a retry. Nothing else from Node is exposed.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("placeiq", {
  onStatus: (callback) => ipcRenderer.on("status", (_event, message) => callback(message)),
  retry: () => ipcRenderer.send("retry"),
  openDockerDownload: () => ipcRenderer.send("open-docker-download"),
});
