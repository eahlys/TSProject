const electron = require('electron')

const { app, BrowserWindow } = require('electron')

function createWindow () {

  const windows = new BrowserWindow({
    width: 1000,
    height: 700,
    webPreferences: {
      nodeIntegration: true
    }
  })

  windows.loadFile('index.html')

  //windows.webContents.openDevTools() //les dev tools
}

app.disableHardwareAcceleration()

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  // Mac os garder actif dans la task bar 1/2
  /*if (process.platform !== 'darwin') {
    app.quit()
  }*/
  app.quit()
})

// app.on('activate', () => {
//   // Mac os garder actif dans la task bar 2/2
//   if (windows === null) {
//     createWindow()
//   }
//
// })