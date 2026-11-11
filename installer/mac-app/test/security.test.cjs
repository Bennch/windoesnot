const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const {quoteShell,quoteApple,validResponse,releaseReady}=require('../security.cjs');
test('paths and tokens remain literal through shell quoting',()=>{
 const value="/tmp/a 'quoted' $(touch should-not-exist) `echo nope`\nfile";
 assert.equal(execFileSync('/bin/sh',['-c','printf %s '+quoteShell(value)],{encoding:'utf8'}),value);
 assert.equal(quoteApple('a"b\\c\nd'),'"a\\"b\\\\c\\nd"');
});
test('responses cannot add lines or terminal control sequences',()=>{
 for(const value of ['',"correct horse battery staple",'pässwörd'])assert.ok(validResponse(value));
 for(const value of ['yes\nreboot','x\ry','\x1b[31m',null,'x'.repeat(2049)])assert.equal(validResponse(value),false);
});
test('only an explicit validated own release enables installation',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'wdn-release-test-'));
 try{
  assert.equal(releaseReady(root),false);
  const data=JSON.stringify({os_list:[{name:'WinDoesNotMac',package:'https://example.org/own.zip'}]});
  fs.writeFileSync(path.join(root,'installer_data.json'),data);
  const config={imageValidated:true,installerBase:'https://example.org/installer',repoBase:'https://example.org/images',metadataSha256:crypto.createHash('sha256').update(data).digest('hex')};
  const python=path.join(root,'Frameworks/Python.framework/Versions/3.13/bin');fs.mkdirSync(python,{recursive:true});fs.writeFileSync(path.join(python,'python3.13'),'fixture');
  fs.writeFileSync(path.join(root,'release.json'),JSON.stringify(config));assert.equal(releaseReady(root),true);
  fs.writeFileSync(path.join(root,'installer_data.json'),data+' ');assert.equal(releaseReady(root),false);
  fs.writeFileSync(path.join(root,'installer_data.json'),data);config.repoBase='http://example.org/images';fs.writeFileSync(path.join(root,'release.json'),JSON.stringify(config));assert.equal(releaseReady(root),false);
 }finally{fs.rmSync(root,{recursive:true,force:true});}
});
