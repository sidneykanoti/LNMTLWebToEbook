import { test } from 'node:test';
import assert from 'node:assert/strict';
import { selectAsset, onRequestGet } from '../functions/download/[platform].js';
test('selects executable packages, ignores checksums and distinguishes Mac chips', () => {
 const names=['windows-x64.exe','windows-x64-self-test.json','macos-arm64.dmg','macos-x64.dmg','linux-x64.deb','linux-x64.tar.gz','linux-x64-SHA256SUMS.txt'];
 const assets=names.map(name=>({name:`LNMTLWebToEbook-2.5.1-${name}`}));
 for(const [platform, suffix] of Object.entries({windows:'windows-x64.exe','mac-arm':'macos-arm64.dmg','mac-intel':'macos-x64.dmg',linux:'linux-x64.tar.gz','linux-deb':'linux-x64.deb'})) assert.equal(selectAsset(assets,platform).name,`LNMTLWebToEbook-2.5.1-${suffix}`);
 assert.equal(selectAsset(assets,'unknown'),undefined);
});
test('rejects an unsupported platform without requesting GitHub',async()=>{assert.equal((await onRequestGet({params:{platform:'unknown'}})).status,404)});
test('redirects to the latest asset and provides a recoverable fallback',async()=>{
 const original=globalThis.fetch;
 try {
 const url='https://github.com/sidneykanoti/LNMTLWebToEbook/releases/download/v2.0.0/app-windows-x64.exe';
 globalThis.fetch=async()=>Response.json({assets:[{name:'app-windows-x64.exe',browser_download_url:url}]});
 const context={params:{platform:'windows'},request:new Request('https://example.com/download/windows')};
 assert.equal((await onRequestGet(context)).headers.get('Location'),url);
 globalThis.fetch=async()=>new Response('',{status:503});
 assert.equal((await onRequestGet(context)).headers.get('Location'),'https://example.com/?download=unavailable#download');
 } finally {globalThis.fetch=original;}
});
