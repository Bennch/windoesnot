const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('installer',Object.freeze({
 status:()=>ipcRenderer.invoke('installer:status'),
 start:language=>ipcRenderer.invoke('installer:start',language),
 demo:()=>ipcRenderer.invoke('installer:demo'),
 answer:value=>ipcRenderer.invoke('installer:answer',value),
 onEvent:callback=>{const listener=(_event,value)=>callback(value);ipcRenderer.on('installer:event',listener);return ()=>ipcRenderer.removeListener('installer:event',listener);}
}));
