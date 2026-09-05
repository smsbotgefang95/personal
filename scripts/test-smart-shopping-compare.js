const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('smart-shopping.html', 'utf8');
const context = vm.createContext({
  priceHistory: {}, productFacts: item => item.facts,
  editStorageKey: (list, key) => `${list}::${key}`,
  editableFactValue: value => value === 'Not listed' ? '' : value || ''
});
vm.runInContext(html.slice(html.indexOf('    const weightUnitAliases ='), html.indexOf('    function splitWeightValue')), context);
for (const name of ['parseDiscountAmount', 'formatMoneyAmount', 'calculateSalePrice', 'parsePriceAmount', 'normalizedWeightQuantity', 'parseWeightQuantity']) {
  const start = html.indexOf(`    function ${name}(`);
  vm.runInContext(html.slice(start, html.indexOf('\n    function ', start + 1)), context);
}
vm.runInContext(html.slice(html.indexOf('    function comparisonUnit('), html.indexOf('    let compareItems =')), context);
const item = {sourceList:'shop',key:'test',stores:['Costco'],facts:{price:'$8',weight:'2 lb'}};
context.priceHistory['shop::test'] = [
  {price:'$3',weight:'16 oz',stores:['Giant'],date:'2026-09-01'},
  {price:'$9',weight:'1 lb',stores:['Target'],date:'2026-09-02'},
  {price:'$1',weight:'1 fl oz',stores:['Volume']},
  {price:'€1',weight:'1 lb',stores:['Euro']}
];
let rows = context.comparisonRows(item);
assert.equal(rows.filter(row => row.best).length, 1);
assert.equal(rows.find(row => row.best).store, 'Giant', 'actual minimum wins, not last price');
assert.equal(rows.find(row => row.best).date, '2026-09-01');
assert.equal(rows[0].unit.amount,4,'uses latest item facts');
assert.equal(rows[0].date,'Date unknown');
context.priceHistory['shop::test'].push({price:'$8',salePrice:'$6',weight:'2 lb',stores:['Sale'],date:'2026-09-03'});
rows=context.comparisonRows(item);
assert.equal(rows.filter(row => row.best).length,2,'ties highlighted including historical sales');
assert.equal(context.comparisonUnit('', '', '$1 / oz').amount,16);
assert.equal(context.comparisonUnit('$1','1 kg','').key,'$::lb');
assert.equal(context.comparisonUnit('€2','1 lb','').key,'€::lb');
assert.equal(context.comparisonUnit('$2','',''),null);
assert.equal(context.comparisonUnit('','$2','not known'),null);
assert.equal(context.comparisonRows({...item,key:'empty',facts:{}}).length,0);
assert.equal(context.comparisonRows({...item,key:'single'})[0].best,false);
assert.ok(!html.includes('openCompare(getSignals()[0]'));
assert.ok(html.includes('data-compare-item'));
for (const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
console.log('PASS: saved prices, numeric minima, ties, history dates, unit conversions, currency isolation, missing prices, script syntax');
