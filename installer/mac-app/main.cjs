'use strict';
const {app,BrowserWindow,ipcMain,dialog,powerSaveBlocker,Menu}=require('electron');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net'),crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const {pathToFileURL}=require('node:url');
const {quoteShell,quoteApple,validResponse,releaseReady}=require('./security.cjs');
let window,connection,server,directory,pending=false,running=false,blocker;
let demoIndex=-1;
if(!app.requestSingleInstanceLock())app.quit();
app.on('second-instance',()=>{if(window){window.restore();window.focus();}});
const backend=path.join(process.resourcesPath,'backend');
function event(value){if(window&&!window.isDestroyed())window.webContents.send('installer:event',value);}
function clean(){connection?.destroy();server?.close();if(directory)fs.rmSync(directory,{recursive:true,force:true});if(blocker!==undefined&&powerSaveBlocker.isStarted(blocker))powerSaveBlocker.stop(blocker);connection=server=directory=undefined;pending=false;running=false;}
function trusted(e){return window&&!window.isDestroyed()&&e.sender===window.webContents&&e.senderFrame===window.webContents.mainFrame;}
function demo(){
 const steps=[{type:'prompt',kind:'choice',label:'Testlauf / Test run: Wähle ein Beispiel / Choose an example',choices:[{value:'example',label:'WinDoesNotMac · Beispieldatenträger / Example disk'}]},
 {type:'prompt',kind:'password',label:'Testpasswort / Test password — keine echten Zugangsdaten / no real credentials',choices:[]},
 {type:'prompt',kind:'continue',label:'Testlauf: Recovery-Anleitung öffnen / Test run: Open the Recovery guide',choices:[]}];
 if(demoIndex<steps.length)event(steps[demoIndex]);else {demoIndex=-1;event({type:'demo-complete'});}
}
async function start(language){
 if(running||demoIndex>=0||!['de','en'].includes(language))throw Error('Invalid installer request');
 if(process.platform!=='darwin'||process.arch!=='arm64'||!releaseReady(backend))throw Error('A validated ARM image and macOS backend are not bundled yet.');
 running=true;blocker=powerSaveBlocker.start('prevent-app-suspension');
 directory=fs.mkdtempSync(path.join(os.tmpdir(),'windoesnot-gui-'));fs.chmodSync(directory,0o700);
 const endpoint=path.join(directory,'ui.sock'),token=crypto.randomBytes(32).toString('hex');
 await new Promise((resolve,reject)=>{
  server=net.createServer(socket=>{
   if(connection){socket.destroy();return;}
   let buffer='',authenticated=false;
   const timer=setTimeout(()=>{if(!authenticated)socket.destroy();},10000);timer.unref();
   socket.on('data',chunk=>{
    buffer+=chunk.toString('utf8');if(buffer.length>2*1024*1024){socket.destroy();return;}
    while(buffer.includes('\n')){
     const end=buffer.indexOf('\n'),line=buffer.slice(0,end);buffer=buffer.slice(end+1);
     let value;try{value=JSON.parse(line);}catch{socket.destroy();return;}
     if(!authenticated){
      if(value.type!=='auth'||typeof value.token!=='string'||!/^[a-f0-9]{64}$/.test(value.token)||!crypto.timingSafeEqual(Buffer.from(value.token),Buffer.from(token))){socket.destroy();return;}
      authenticated=true;clearTimeout(timer);connection=socket;event({type:'connected'});continue;
     }
     if(value.type==='prompt')pending=true;
     if(value.type==='exit'){event(value);clean();return;}
     if(value.type==='guide'&&typeof value.html==='string'&&value.html.length<500000){const file=path.join(directory,'guide.html');fs.writeFileSync(file,value.html,{mode:0o600});event({type:'guide',url:pathToFileURL(file).href});}
     else if(['prompt','stage','output','completed'].includes(value.type))event(value);
    }
   });
   socket.on('error',()=>{});
   socket.on('close',()=>{clearTimeout(timer);if(running&&connection===socket){event({type:'error',text:'Connection lost. Do not restart or power off while the backend may still be working.'});connection=undefined;}});
  });server.once('error',reject);server.listen(endpoint,()=>{fs.chmodSync(endpoint,0o600);resolve();});
 });
 const command=['/bin/sh',path.join(backend,'install.sh'),'--gui-socket',endpoint,'--gui-token',token,'--gui-uid',String(process.getuid()),'--gui-language',language].map(quoteShell).join(' ');
 const source='do shell script '+quoteApple(command)+' with administrator privileges';
 // Use Apple's authorization dialog, never collect the sudo password in HTML.
 const auth=spawn('/usr/bin/osascript',['-e',source],{stdio:['ignore','ignore','pipe']});
 let error='';auth.stderr.on('data',data=>{error=(error+data.toString()).slice(-8000);});
 auth.on('error',()=>{event({type:'error',retryable:true,text:'Could not open macOS authorization.'});clean();});
 auth.on('exit',code=>{if(running&&!connection){event({type:'error',retryable:true,text:code===0?'The installer connection closed.':'Authorization or backend startup failed. '+error});clean();}});
}
app.whenReady().then(()=>{
 Menu.setApplicationMenu(Menu.buildFromTemplate([{role:'appMenu'},{role:'editMenu'},{role:'windowMenu'}]));
 window=new BrowserWindow({width:1180,height:900,minWidth:760,minHeight:620,backgroundColor:'#111315',title:'WinDoesNotMac',webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
 window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
 window.webContents.on('will-navigate',e=>e.preventDefault());
 window.webContents.on('before-input-event',(e,input)=>{if(running&&(input.key==='F5'||((input.meta||input.control)&&input.key.toLowerCase()==='r')))e.preventDefault();});
 window.on('close',e=>{if(running){e.preventDefault();dialog.showMessageBox(window,{type:'info',message:'Installation läuft / Installation in progress',detail:'Keep this window open until the installer has finished. / Bitte bis zum Abschluss geöffnet lassen.',buttons:['OK']});}});
 window.loadFile(path.join(__dirname,'ui/index.html'));
 ipcMain.handle('installer:status',e=>{if(!trusted(e))throw Error('Untrusted frame');return {ready:process.platform==='darwin'&&process.arch==='arm64'&&releaseReady(backend),platform:process.platform,guideURL:pathToFileURL(path.join(process.resourcesPath,'assets/guide.html')).href};});
 ipcMain.handle('installer:start',async(e,language)=>{if(!trusted(e))throw Error('Untrusted frame');try{await start(language);}catch(error){if(!connection)clean();throw error;}});
 ipcMain.handle('installer:demo',e=>{if(!trusted(e)||running||demoIndex>=0)throw Error('Installer busy');demoIndex=0;demo();});
 ipcMain.handle('installer:answer',(e,value)=>{if(!trusted(e)||!validResponse(value))throw Error('Invalid response');if(demoIndex>=0){demoIndex++;demo();return true;}if(!pending||!connection)throw Error('No response is pending');pending=false;connection.write(JSON.stringify({text:value})+'\n');return true;});
});
app.on('window-all-closed',()=>{if(!running){clean();app.quit();}});
