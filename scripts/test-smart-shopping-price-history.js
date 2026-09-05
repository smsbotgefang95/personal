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
  vm.runInContext(html.slice(html.indexOf('    const weightUnitAliases ='), html.indexOf('    function splitWeightValue')), context);
  for (const name of ['parseDiscountAmount', 'formatMoneyAmount', 'calculateSalePrice', 'parsePriceAmount', 'normalizedWeightQuantity', 'parseWeightQuantity', 'calculateUnitPrice']) {
    const start = html.indexOf(`    function ${name}(`);
    vm.runInContext(html.slice(start, html.indexOf('\n    function ', start + 1)), context);
  }
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
assert.ok(markup.indexOf('Lowest recorded unit price') < markup.indexOf('<details'), 'sale is prominent outside history');
assert.ok(markup.includes('$2.00 / lb'));
assert.ok(markup.includes('Sale ·'));
assert.equal((afterReload.cardPriceHistoryMarkup({sourceList:'shop',key:'sale',facts:sale}).match(/Lowest recorded unit price/g) || []).length, 1, 'one benchmark even when current sale matches history');
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

// Choose the cheapest observation rather than the latest sale; normalize package sizes.
afterReload.mergePriceHistory({'shop::benchmark':[
  {id:'old', price:'$4', salePrice:'$2', weight:'2 lb', stores:['Old store'], date:'2026-08-01'},
  {id:'recent', price:'$4', salePrice:'$3', weight:'16 oz', stores:['New store'], date:'2026-09-01'},
  {id:'volume', unitPrice:'$0.10 / fl oz', stores:['Volume store'], date:'2026-09-02'}
]});
const benchmark = afterReload.cardPriceHistoryMarkup({sourceList:'shop',key:'benchmark',facts:updated,stores:['Costco']});
assert.ok(benchmark.includes('<strong>$1.00 / lb</strong>'));
assert.ok(benchmark.includes('Sale · 2026-08-01 · Old store'));
assert.equal((benchmark.match(/Lowest recorded unit price/g) || []).length, 2, 'incompatible units stay separate');
const currentBest = afterReload.cardPriceHistoryMarkup({sourceList:'shop',key:'benchmark',facts:{price:'$1',weight:'2 lb'},stores:['Current store']});
assert.ok(currentBest.includes('<strong>$0.50 / lb</strong>'));
assert.ok(currentBest.includes('Regular price · Date unknown · Current store'));
const table = afterReload.priceHistoryTableMarkup([
  {price:'$4',salePrice:'$2',weight:'2 lb'}, {price:'$6',weight:'2 lb'},
  {price:'$4',salePrice:'$2',unitPrice:'$4 / lb'}
]);
assert.ok(!table.includes('<th>Sale unit price</th>'));
assert.ok(table.includes('$1.00 / lb<span class="history-sale-label">Sale</span>'));
assert.ok(table.includes('<td>$3.00 / lb</td>'));
assert.ok(table.includes('Not listed<span class="history-sale-label">Sale</span>'), 'unknown sale unit price must not use regular unit price');
assert.equal((table.match(/<th>/g) || []).length, 6);
console.log('PASS: lowest benchmark, current regular bargain, units, provenance and simplified sale history');
