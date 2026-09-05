const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const html = fs.readFileSync('smart-shopping.html', 'utf8');
const code = html.slice(html.indexOf('    const priceHistoryStorageKey ='), html.indexOf('    function normalizeStoredItem('));
const server = { data: { itemAdds: { '买菜': [{key:'old',name:'白菜'}] } } };
function device(storage = new Map()) {
  const localStorage = {getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)};
  const c = vm.createContext({localStorage,window:{localStorage,setTimeout:()=>1,clearTimeout(){}},document:{getElementById:()=>({})},render(){},fetch:async(_,o)=>{
    if(o.method==='POST') { if(server.fail) return {ok:false,status:503}; server.data=JSON.parse(o.body); if(server.onPost)server.onPost(); return {ok:true}; }
    return {ok:true,json:async()=>JSON.parse(JSON.stringify(server.data))};
  }});
  vm.runInContext(code+'\nshoppingSyncKey="test";',c);
  return {storage,sync:()=>c.syncShoppingDevices(),add:(key,name)=>vm.runInContext(`(itemAdds['买菜'] ||= []).push(${JSON.stringify({key,name})});saveItemAdds()`,c),items:()=>JSON.parse(vm.runInContext('JSON.stringify(itemAdds)',c)),remove:key=>vm.runInContext(`itemRemovals['买菜::${key}']=true;saveItemRemovals();itemAdds['买菜']=itemAdds['买菜'].filter(i=>i.key!==${JSON.stringify(key)});saveItemAdds()`,c)};
}
(async()=>{
  const a=device(); await a.sync(); a.add('beef','牛腩'); await a.sync();
  assert.equal(a.items()['买菜'].filter(i=>i.name==='牛腩').length,1);
  const b=device(); await b.sync(); assert.equal(b.items()['买菜'].filter(i=>i.name==='牛腩').length,1);
  a.add('retry','萝卜'); server.fail=true; await a.sync(); const reload=device(a.storage); server.fail=false; await reload.sync();
  assert.ok(server.data.itemAdds['买菜'].some(i=>i.key==='retry'));
  a.add('one','姜'); b.add('two','蒜'); await a.sync(); await b.sync();
  assert.ok(server.data.itemAdds['买菜'].some(i=>i.key==='one')); assert.ok(server.data.itemAdds['买菜'].some(i=>i.key==='two'));
  b.remove('beef'); await b.sync(); assert.equal(server.data.itemRemovals['买菜::beef'],true);
  console.log('PASS: 牛腩 survives stale server sync, second device, failed upload/reload, concurrent additions; deleted items retain removal markers');
})().catch(e=>{console.error(e);process.exitCode=1});
