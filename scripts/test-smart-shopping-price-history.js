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
    escapeHtml: value => String(value).replaceAll('<', '&lt;'),
    editStorageKey: (list, key) => `${list}::${key}`,
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
assert.equal(history().length,3,'sale-only save retains sale history');
reloaded.recordRegularPrice('item',{...item,facts:{...updated,salePrice:'$3.99'}},{...updated,weight:'3 lb'},['Costco'],'2026-09-07');
assert.equal(history().length,4,'ending a sale retains old sale and package');
reloaded.mergePriceHistory({item:[history()[0],{id:'remote',date:'2026-09-08',price:'$6.49',stores:['Giant'],weight:'3 lb'}]});
assert.equal(history().length,5,'merge retains local and remote entries, without duplicate baseline');
assert.equal(history()[4].stores[0],'Giant');
console.log('PASS: previous price, dates, reload, sale-only save, package change and offline history merge');

const sale = {...item.facts, salePrice:'$3.99', saleUnitPrice:'$2.00 / lb'};
reloaded.recordRegularPrice('shop::sale', {...item,facts:sale}, updated, ['Costco'], '2026-09-09');
let savedSale = JSON.parse(storage.get('smart-shopping-price-history-v1'))['shop::sale'];
assert.equal(savedSale[0].saleUnitPrice, '$2.00 / lb', 'regular price update preserves previous sale');
assert.equal(savedSale[1].saleUnitPrice, '', 'old sale is not an active sale');
const afterReload = device();
const markup = afterReload.cardPriceHistoryMarkup({sourceList:'shop',key:'sale',facts:updated});
assert.ok(markup.indexOf('Last saved sale unit price') < markup.indexOf('<details'), 'sale is prominent outside history');
assert.ok(markup.includes('$2.00 / lb'));
assert.ok(markup.includes('Historical sale'));
assert.ok(!afterReload.cardPriceHistoryMarkup({sourceList:'shop',key:'sale',facts:sale}).includes('Last saved sale unit price'), 'current sale does not get duplicate historical banner');
// Upgrade an existing regular-only history without losing a current sale.
afterReload.mergePriceHistory({'shop::legacy':[{id:'legacy',...item.facts,stores:['Costco'],date:'2026-09-01'}]});
afterReload.recordRegularPrice('shop::legacy', {...item,facts:sale}, updated, ['Costco'], '2026-09-09');
const legacy = JSON.parse(storage.get('smart-shopping-price-history-v1'))['shop::legacy'];
assert.equal(legacy.length,3);
assert.equal(legacy[1].saleUnitPrice,'$2.00 / lb');
assert.equal(legacy[1].date,null,'do not invent a date for an unsaved previous sale');
const before = legacy.length;
afterReload.recordRegularPrice('shop::legacy', {...item,facts:updated}, updated, ['Costco'], '2026-09-10');
assert.equal(JSON.parse(storage.get('smart-shopping-price-history-v1'))['shop::legacy'].length,before);
console.log('PASS: sale retention, visible historical highlight, reload, legacy history and unchanged saves');

// Completing details, including the package corrections from the reported soy sauce item,
// must not create dated price observations or alter existing historical evidence.
const incomplete = {stores:['Great Wall'], facts:{price:'$3.99'}};
const largePackage = {...incomplete.facts,weight:'250 fl oz',unitPrice:'$0.02 / fl oz'};
const correctedPackage = {...largePackage,weight:'20 fl oz',unitPrice:'$0.20 / fl oz'};
const beforeDetails = storage.get('smart-shopping-price-history-v1');
afterReload.recordRegularPrice('soy', incomplete, largePackage, ['Great Wall'], '2026-09-05');
afterReload.recordRegularPrice('soy', {...incomplete,facts:largePackage}, correctedPackage, ['Great Wall'], '2026-09-05');
afterReload.recordRegularPrice('soy', {...incomplete,facts:correctedPackage}, correctedPackage, ['Giant'], '2026-09-06');
afterReload.recordRegularPrice('shop::legacy', {...item,facts:updated}, {...updated,weight:'20 oz',unitPrice:'$4.39 / lb'}, ['Giant'], '2026-09-10');
assert.equal(storage.get('smart-shopping-price-history-v1'),beforeDetails,'detail-only saves leave all history unchanged');
afterReload.recordRegularPrice('format', {...item,facts:{price:'$4.90'}}, {price:'$4.9'}, ['Costco'], '2026-09-10');
assert.equal(storage.get('smart-shopping-price-history-v1'),beforeDetails,'equivalent price formatting is not a price change');
afterReload.recordRegularPrice('soy', {...incomplete,facts:correctedPackage}, {...correctedPackage,price:'$4.99'}, ['Great Wall'], '2026-09-07');
const soy = JSON.parse(storage.get('smart-shopping-price-history-v1')).soy;
assert.equal(soy.length,2);
assert.equal(soy[0].weight,'20 fl oz','first real change preserves completed package details');
assert.equal(soy[1].price,'$4.99');
afterReload.recordRegularPrice('discount', item, {...item.facts,discount:'$1 off'}, ['Costco'], '2026-09-10');
assert.equal(JSON.parse(storage.get('smart-shopping-price-history-v1')).discount.length,2,'discount changes still create history');
console.log('PASS: package completion, package correction, store edits, existing history, equivalent prices and real price/discount changes');
