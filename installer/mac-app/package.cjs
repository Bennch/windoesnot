'use strict';
const fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process');
const {releaseReady}=require('./security.cjs');
async function main(){
 const packager=(await import('@electron/packager')).packager;
 const root=__dirname,assets=path.join(root,'assets');fs.mkdirSync(assets,{recursive:true});
 execFileSync('python3',[path.join(root,'../asahi/src/recovery_guide.py'),'--output',path.join(assets,'guide.html')]);
 execFileSync('python3',[path.join(root,'../../tools/build-mac-icon.py'),path.join(assets,'WinDoesNotMac.icns')]);
 const extraResource=[assets];
 const backend=process.env.WINDOESNOT_MAC_BACKEND;
 if(backend){if(path.basename(backend)!=='backend'||!releaseReady(backend))throw Error('Supply a validated backend/ tree, including release.json and installer_data.json');extraResource.push(path.resolve(backend));}
 const output=await packager({dir:root,name:'WinDoesNotMac Installer',platform:'darwin',arch:'arm64',electronVersion:'45.3.0',out:path.join(root,'../../out/mac-app'),overwrite:true,asar:true,icon:path.join(assets,'WinDoesNotMac.icns'),appBundleId:'org.windoesnot.mac.installer',appCategoryType:'public.app-category.utilities',extraResource,ignore:[/^\/node_modules\/(?:electron|@electron)/,/^\/assets/,/^\/test/,/^\/dist/],osxSign:false,osxNotarize:false});
 console.log(output.join('\n'));console.log(backend?'Backend bundled; macOS hardware testing still required.':'Preview app: installation disabled until the validated backend/image is bundled.');
}
main().catch(error=>{console.error(error.message);process.exit(1);});
