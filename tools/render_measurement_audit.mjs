#!/usr/bin/env node
// Raw visible crops only. No OCR, app access or network. Labels see original colors.
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),sharp=require('../viewer/node_modules/sharp');sharp.concurrency(1);
const manifest=path.resolve(process.argv[2]||'');
if(!process.argv[2]||fs.statSync(manifest).size>4*1024*1024)throw Error('Bounded render-input.json required');
const root=fs.realpathSync(path.dirname(manifest)),task=JSON.parse(fs.readFileSync(manifest,'utf8'));
if(task.schema_version!==1||!Array.isArray(task.samples)||task.samples.length>900||task.frames.length>20)throw Error('Unsupported audit scope');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex'),frames=new Map();
for(const f of task.frames){
 if(!/^[a-f0-9]{64}$/.test(f.source_sha256)||f.evidence_file!==`evidence/${f.source_sha256}.png`)throw Error('Unsafe frame path');
 const file=fs.realpathSync(path.join(root,f.evidence_file));if(!file.startsWith(root+path.sep)||fs.statSync(file).size>16*1024*1024)throw Error('Evidence escape/size');
 const bytes=fs.readFileSync(file),meta=await sharp(bytes).metadata();
 if(hash(bytes)!==f.source_sha256||meta.format!=='png'||meta.width!==3440||meta.height!==1440)throw Error('Source integrity/layout mismatch');frames.set(f.source_sha256,bytes);
}
for(const s of task.samples){
 if(!/^[a-f0-9]{64}$/.test(s.sample_id)||s.crop_file!==`crops/${s.sample_id}.png`||!frames.has(s.source_sha256))throw Error('Unsafe crop path');
 const r=s.source_rect;
 if(!['x','y','width','height'].every(k=>Number.isInteger(r[k]))||r.x<0||r.y<0||r.width<=0||r.height<=0||r.width>125||r.height>35||r.x+r.width>3440||r.y+r.height>1440)throw Error('Invalid visible crop');
 const target=path.join(root,s.crop_file);if(fs.realpathSync(path.dirname(target))!==path.join(root,'crops'))throw Error('Crop destination escape');
 const bytes=await sharp(frames.get(s.source_sha256)).removeAlpha().extract({left:r.x,top:r.y,width:r.width,height:r.height}).resize(r.width*4,r.height*4,{kernel:'lanczos3'}).png().toBuffer();
 fs.writeFileSync(target,bytes,{flag:'wx',mode:0o600});
}
console.log(`Prepared ${task.samples.length} raw audit crops; no OCR performed.`);
