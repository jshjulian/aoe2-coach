#!/usr/bin/env node
// Research only: prepare VISIBLE, saved CaptureAge HUD pixels for local OCR.
// Not a game/CA interface. Fixed observed 1.26 layout; no hidden/blurred fields.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const sharp = require('../viewer/node_modules/sharp');
sharp.concurrency(1);
const [input, output] = process.argv.slice(2);
if (!input || !output) throw new Error('Usage: node tools/prepare_state_ocr.mjs saved-window.png new-ocr-sheet.png');
if (path.resolve(input) === path.resolve(output) || fs.existsSync(output) || fs.existsSync(output+'.layout.json')) throw new Error('Refusing to overwrite input/existing research files.');
const bytes = fs.readFileSync(input);
const size = await sharp(bytes).metadata();
if (size.width !== 3440 || size.height !== 1440) throw new Error('Unsupported layout/resolution. Do not guess field locations.');
const fields = [
  ['left_wood',750,0,76,34], ['left_food',875,0,76,34], ['left_gold',1000,0,76,34], ['left_stone',1125,0,76,34],
  ['right_wood',2295,0,76,34], ['right_food',2420,0,76,34], ['right_gold',2545,0,76,34], ['right_stone',2670,0,76,34],
  ['clock',1680,165,110,35],
];
const rowHeight = 130;
const overlays = [];
for (let i=0;i<fields.length;i++) {
  const [name,left,top,width,height] = fields[i];
  const label = Buffer.from(`<svg width="330" height="120"><rect width="100%" height="100%" fill="white"/><text x="5" y="80" font-family="Arial" font-size="46" fill="black">${name}</text></svg>`);
  const pixels = await sharp(bytes).removeAlpha().extract({left,top,width,height}).resize({width:width*3,height:height*3,kernel:'nearest'}).greyscale().threshold(180).negate().png().toBuffer();
  overlays.push({input:label,left:0,top:i*rowHeight},{input:pixels,left:360,top:i*rowHeight+8});
}
const identityPatches=[];
for (const [role,left,top,width,height] of [['left',1350,0,350,45],['right',1800,0,310,45]]) {
  const pixels=await sharp(bytes).removeAlpha().extract({left,top,width,height}).raw().toBuffer();
  identityPatches.push({role,rect:{left,top,width,height},rgb_sha256:crypto.createHash('sha256').update(pixels).digest('hex')});
}
const result = await sharp({create:{width:760,height:rowHeight*fields.length,channels:3,background:'white'}}).composite(overlays).png().toBuffer();
fs.writeFileSync(output,result,{flag:'wx'});
fs.writeFileSync(output+'.layout.json',JSON.stringify({schema_version:1,qualification:'research_only_ocr_not_verified_game_state',
  layout:'observed_CaptureAge_1.26_3440x1440_two_player_HUD', identity_patches:identityPatches,
  identity_note:'Pixel continuity witness only. Operator must bind the full visible HUD/replay to content/player identity; not automatic parser facts.', source_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),
  ocr_image_sha256:crypto.createHash('sha256').update(result).digest('hex'),
  notes:['Left/right are UI roles, NOT parser player numbers. Names/content identity require explicit verification.',
         'Only visible stockpile numbers and clock. No inactive/blurred/paid controls read.',
         'OCR can silently misread valid digits. No confidence score or state qualification is provided.'],
  fields:fields.map(([name,x,y,width,height],i)=>({name,source_rect:{x,y,width,height},ocr_rect:{x:360,y:i*rowHeight+8,width:width*3,height:height*3}}))},null,2)+'\n',{flag:'wx'});
console.log(`Research-only OCR sheet: ${output}`);
