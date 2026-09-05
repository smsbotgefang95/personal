const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('smart-shopping.html','utf8');
const code=html.slice(html.indexOf('    const itemEditsStorageKey ='),html.indexOf('    function normalizeStoredItem('));
const move=html.slice(html.indexOf('    function moveItemToList('),html.indexOf('    function deleteItem('));
const id='冰柜_肉和其他🥩::杂豆和豆制品::Organic edamame 有机毛豆';
const server={data:{itemMoves:{[id]:'买菜'}}};
function device(storage=new Map()) {
 const localStorage={getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)};
 const c=vm.createContext({localStorage,window:{localStorage,setTimeout:()=>1,clearTimeout(){}},document:{getElementById:()=>({})},render(){},showToast(){},clearDropTargets(){},state:{},els:{search:{}},listNames:['买菜','冰柜'],findSourceItem:()=>({name:'Organic edamame 有机毛豆'}),getImportedItems:()=>[],displayItemName:i=>i.name,fetch:async(_,o)=>{if(o.method==='POST'){if(server.fail)return {ok:false,status:503};server.data=JSON.parse(o.body);if(server.onPost)server.onPost();return {ok:true};}return {ok:true,json:async()=>JSON.parse(JSON.stringify(server.data))};}});
 vm.runInContext(code+move+'\nshoppingSyncKey="test"; function itemTargetList(s,k){return itemMoves[moveStorageKey(s,k)] || "冰柜";}',c);
 return {storage,move:target=>c.moveItemToList('冰柜_肉和其他🥩','杂豆和豆制品::Organic edamame 有机毛豆',target),sync:()=>c.syncShoppingDevices(),target:()=>c.itemTargetList('冰柜_肉和其他🥩','杂豆和豆制品::Organic edamame 有机毛豆'),pending:()=>JSON.parse(storage.get('smart-shopping-pending-moves-v1')||'{}')};
}
(async()=>{const a=device();await a.sync();a.move('冰柜');await a.sync();assert.equal(a.target(),'冰柜');assert.equal(server.data.itemMoves[id],'冰柜');assert.deepEqual(a.pending(),{});const b=device();await b.sync();assert.equal(b.target(),'冰柜');a.move('买菜');server.fail=true;await a.sync();assert.equal(a.pending()[id],'买菜');const reload=device(a.storage);server.fail=false;await reload.sync();assert.equal(server.data.itemMoves[id],'买菜');reload.move('冰柜');server.onPost=()=>reload.move('买菜');await reload.sync();assert.equal(reload.pending()[id],'买菜');server.onPost=null;await reload.sync();assert.equal(server.data.itemMoves[id],'买菜');console.log('PASS: move with stale server location, second device, failed upload/reload, move during upload');})().catch(e=>{console.error(e);process.exitCode=1});
