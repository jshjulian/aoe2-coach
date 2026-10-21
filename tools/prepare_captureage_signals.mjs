#!/usr/bin/env node
// Research-only visible saved-image extraction. No app interface/control or paid-field decoding.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),sharp=require('../viewer/node_modules/sharp');sharp.concurrency(1);
const [input,output]=process.argv.slice(2);
if(!input||!output)throw Error('Usage: saved-full-HUD.png new-signals-sheet.png');
if(path.resolve(input)===path.resolve(output)||fs.existsSync(output)||fs.existsSync(output+'.layout.json'))throw Error('Refusing existing outputs');
if(fs.statSync(input).size>16*1024*1024)throw Error('Saved HUD PNG exceeds 16MB');
const bytes=fs.readFileSync(input),size=await sharp(bytes).metadata();
if(size.format!=='png'||size.width!==3440||size.height!==1440)throw Error('Only observed 1.26 3440x1440 PNG layout supported');
const fields=[];
function add(name,x,y,width,height,kind='integer'){fields.push({name,source_rect:{x,y,width,height},kind,preprocessing:'lanczos3_grayscale_negative'});}
for(const [side,base] of [['left',750],['right',2295]])for(const [i,r] of ['wood','food','gold','stone'].entries()){
 add(`${side}_resource_${r}`,base+125*i,0,76,34);
 add(`${side}_workers_on_${r}`,base+125*i,35,76,26);
}
add('clock',1660,165,125,35,'duration');
for(const [side,pop,mil,worker,idle] of [['left',1347,1550,1545,1460],['right',2047,1865,1860,1950]]){
 add(`${side}_population_used`,pop,96,50,23);add(`${side}_population_limit`,pop,124,50,25);
 add(`${side}_military_count`,mil,96,side==='right'?37:52,23);add(`${side}_economic_unit_count`,worker,124,side==='right'?43:57,25);
 add(`${side}_idle_workers`,idle,124,side==='left'?36:50,25);
}
for(const [side,y] of [['left',1323],['right',1384]]){
 add(`${side}_tc_idle_seconds`,3215,y,105,25,'duration');
 add(`${side}_housed_seconds`,3215,y+26,105,25,'duration');
 add(`${side}_army_value`,3008,y,90,25);
 add(`${side}_relic_gold_collected`,3110,y,100,25);
 add(`${side}_relic_count`,3155,y+26,55,25);
 add(`${side}_unit_kills`,2695,y,70,25);
 add(`${side}_unit_deaths`,2695,y+26,70,25);
 add(`${side}_eco_kills`,2810,y,75,25);
 add(`${side}_eco_deaths`,2810,y+26,75,25);
}
const rowHeight=120,colWidth=750,rows=Math.ceil(fields.length/2),overlays=[];
fields.forEach((f,i)=>{f.ocr_rect={x:Math.floor(i/rows)*colWidth+360,y:(i%rows)*rowHeight+8,width:f.source_rect.width*3,height:f.source_rect.height*3};});
for(let i=0;i<fields.length;i++){
 const f=fields[i],col=Math.floor(i/rows)*colWidth,row=(i%rows)*rowHeight;
 const label=Buffer.from(`<svg width="340" height="110"><rect width="100%" height="100%" fill="white"/><text x="3" y="65" font-family="Arial" font-size="25" fill="black">${f.name}</text></svg>`);
 const p=await sharp(bytes).removeAlpha().extract({left:f.source_rect.x,top:f.source_rect.y,width:f.source_rect.width,height:f.source_rect.height}).resize(f.ocr_rect.width,f.ocr_rect.height,{kernel:'lanczos3'}).greyscale().negate().png().toBuffer();
 overlays.push({input:label,left:col,top:row},{input:p,left:f.ocr_rect.x,top:f.ocr_rect.y});
}
const image=await sharp({create:{width:1500,height:rows*rowHeight,channels:3,background:'white'}}).composite(overlays).png().toBuffer();
fs.writeFileSync(output,image,{flag:'wx',mode:0o600});
fs.writeFileSync(output+'.layout.json',JSON.stringify({schema_version:1,layout:'observed_CA_1.26_3440x1440_signals_v3',extractor_version:'research-visible-signals-v3',runtime:{node:process.version,sharp:sharp.versions.sharp,libvips:sharp.versions.vips},width:1500,height:rows*rowHeight,source_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),ocr_image_sha256:crypto.createHash('sha256').update(image).digest('hex'),fields,validated_for_application:false,qualification:'research_only_visible_signals_not_verified_game_state'},null,2),{flag:'wx',mode:0o600});
console.log(output);
