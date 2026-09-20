const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const html = fs.readFileSync('smart-shopping.html', 'utf8');
const start = html.indexOf('    function openDuplicateStoreEditor(');
const end = html.indexOf('    function openItemMover(', start);
assert.ok(start >= 0 && end > start, 'duplicate-store editor function is present');

const fields = () => Object.fromEntries([
  'stores', 'price', 'discount', 'sale-price', 'weight', 'weight-unit',
  'count', 'unit-price', 'sale-unit-price', 'date'
].map(name => [name, { value: '', focus() {} }]));
const row = values => {
  const controls = fields();
  Object.assign(controls.stores, { value: values?.store || '' });
  return { controls, querySelector(selector) { return controls[selector.match(/"(.+)"/)[1]]; } };
};

const status = { textContent: '' };
const context = vm.createContext({
  storePriceDrafts: [],
  openItemEditor() {},
  canonicalStoresFromInput: value => String(value || '').split(',').map(v => v.trim()).filter(Boolean),
  addStorePriceSection() { context.storePriceDrafts.push({ row: row() }); },
  editableFactValue: value => value || '',
  splitWeightValue: value => value === '3 lb (6 count)' ? { amount: '3', unit: 'lb', count: '6' } : { amount: '', unit: '', count: '' },
  markItemEditDirty() { context.dirty = true; },
  document: { getElementById: () => status },
  showToast(message) { context.toast = message; },
  window: { requestAnimationFrame(callback) { callback(); } }
});
vm.runInContext(html.slice(start, end), context);

context.openDuplicateStoreEditor({}, {
  price: '$8.99', discount: '10%', salePrice: '$8.09', weight: '3 lb (6 count)',
  unitPrice: '$3.00 / lb', saleUnitPrice: '$2.70 / lb'
}, ['Giant'], '2026-09-20');
assert.equal(context.storePriceDrafts.length, 1);
assert.deepEqual(
  Object.fromEntries(Object.entries(context.storePriceDrafts[0].row.controls).map(([key, value]) => [key, value.value])),
  { stores: 'Giant', price: '$8.99', discount: '10%', 'sale-price': '$8.09', weight: '3', 'weight-unit': 'lb', count: '6', 'unit-price': '$3.00 / lb', 'sale-unit-price': '$2.70 / lb', date: '2026-09-20' }
);
assert.equal(context.dirty, true);
assert.match(status.textContent, /already exists/i);
assert.match(context.toast, /other store/i);

const existing = { row: row({ store: 'Costco' }) };
context.storePriceDrafts = [existing];
context.openDuplicateStoreEditor({}, { price: '$7.50', weight: '2 lb' }, ['Costco'], '2026-09-21');
assert.equal(context.storePriceDrafts.length, 1, 'an existing store section is reused');
assert.equal(existing.row.controls.price.value, '$7.50');
assert.equal(existing.row.controls.date.value, '2026-09-21');

console.log('PASS: duplicate item redirects to one reusable store-price section and preserves entered values');
