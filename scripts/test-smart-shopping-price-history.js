const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const html = fs.readFileSync('smart-shopping.html', 'utf8');
const code = html.slice(html.indexOf('    const priceHistoryStorageKey ='), html.indexOf('    const itemEditsStorageKey ='));
const storage = new Map();
function device() {
  const context = vm.createContext({
    localStorage: { getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v) },
    crypto: { randomUUID }, productFacts: item => item.facts,
    editableFactValue: value => value === 'Not listed' ? '' : value || '',
    defaultPriceCurrency: value => value,
    parseWeightQuantity: value => value.replace(/\s/g, '')
  });
  vm.runInContext(code, context);
  return context;
}
const item = {stores:['Costco'], facts:{price:'$4.99',weight:'2 lb',unitPrice:'$2.50 / lb'}};
const updated = {...item.facts,price:'$5.49',unitPrice:'$2.75 / lb'};
const first = device();
first.recordRegularPrice('item', item, updated, ['Costco'], '2026-09-05');
const history = () => JSON.parse(storage.get('smart-shopping-price-history-v1')).item;
assert.equal(history().length,2);
assert.equal(history()[0].date,null);
assert.equal(history()[1].price,'$5.49');
const reloaded = device();
reloaded.recordRegularPrice('item',{...item,facts:updated},{...updated,salePrice:'$3.99'},['Costco'],'2026-09-06');
assert.equal(history().length,2,'sale-only save must not add regular history');
reloaded.recordRegularPrice('item',{...item,facts:updated},{...updated,weight:'3 lb'},['Costco'],'2026-09-07');
assert.equal(history().length,3,'package changes retain old package');
reloaded.mergePriceHistory({item:[history()[0],{id:'remote',date:'2026-09-08',price:'$6.49',stores:['Giant'],weight:'3 lb'}]});
assert.equal(history().length,4,'merge retains local and remote entries, without duplicate baseline');
assert.equal(history()[3].stores[0],'Giant');
console.log('PASS: previous price, dates, reload, sale-only save, package change and offline history merge');
