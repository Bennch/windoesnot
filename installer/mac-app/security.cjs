'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
function quoteShell(value){return "'"+value.replaceAll("'","'\\''")+"'";}
function quoteApple(value){return '"'+value.replaceAll('\\','\\\\').replaceAll('"','\\"').replaceAll('\n','\\n').replaceAll('\r','\\r')+'"';}
function validResponse(value){return typeof value==='string'&&value.length<=2048&&!/[\x00-\x1f\x7f]/u.test(value);}
function releaseReady(root){
 try{
  const r=JSON.parse(fs.readFileSync(path.join(root,'release.json'),'utf8'));
  if(r.imageValidated!==true)return false;
  for(const key of ['installerBase','repoBase']){const u=new URL(r[key]);if(u.protocol!=='https:'||u.username||u.password)return false;}
  const content=fs.readFileSync(path.join(root,'installer_data.json'));
  if(crypto.createHash('sha256').update(content).digest('hex')!==r.metadataSha256)return false;
  const entries=JSON.parse(content).os_list;
  return Array.isArray(entries)&&entries.length>0&&entries.every(e=>typeof e.name==='string'&&e.name.startsWith('WinDoesNotMac'))&&fs.existsSync(path.join(root,'Frameworks/Python.framework/Versions/3.13/bin/python3.13'));
 }catch{return false;}
}
module.exports={quoteShell,quoteApple,validResponse,releaseReady};
