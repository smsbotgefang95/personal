const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('smart-shopping.html', 'utf8');
const section = (start, end) => html.slice(html.indexOf(start), html.indexOf(end));
const fields = {};
const field = key => fields[key] ||= { value: '', dataset: {}, setCustomValidity(value) { this.error = value; }, reportValidity() {} };
const context = vm.createContext({
  canonicalizeShoppingText: value => String(value || ''),
  displayProductName: value => String(value || ''), itemBrand: item => item.brand || '',
  formatProductName: value => value, document: { getElementById: field },
  els: new Proxy({}, { get: (_, key) => field(key) }),
  editSession: { mode: 'add', list: '买菜', key: '', photo: '' },
  listNames: ['买菜'], itemAdds: {}, itemEdits: {}, pendingEdits: {}, parsedByList: {},
  getImportedItems: () => [], getSourceItems: () => [],
  defaultPriceCurrency: value => value, defaultDiscountValue: value => value,
  editableWeightValue: () => '', canonicalStoresFromInput: () => ['Costco'],
  editStorageKey: (list, key) => `${list}::${key}`,
  recordRegularPrice() {}, saveItemAdds() {}, savePendingEdits() {}, saveItemEdits() {},
  closeItemEditor() {}, render() {}, showToast() {}, syncShoppingDevices() {},
  displayListName: value => value
});
vm.runInContext(section('    function itemNames(', '    const photoByName'), context);
vm.runInContext(section('    function saveItemEdit(', '\n    function render()'), context);
const names = item => JSON.parse(JSON.stringify(context.itemNames(item)));
assert.deepEqual(names({name:'Organic cucumber 有机黄瓜'}), {englishName:'Organic cucumber',chineseName:'有机黄瓜'});
assert.deepEqual(names({name:'黄瓜'}), {englishName:'',chineseName:'黄瓜'});
assert.deepEqual(names({name:'Cucumber'}), {englishName:'Cucumber',chineseName:''});
assert.deepEqual(names({name:'Tea 茶 Green'}), {englishName:'Tea 茶 Green',chineseName:''});
assert.deepEqual(names({name:'Old 旧', englishName:'',chineseName:'新'}), {englishName:'',chineseName:'新'});
field('price-effective-date').value = '2026-09-05';
context.saveItemEdit({preventDefault(){}});
assert.match(field('editName').error, /English or Chinese/);
assert.equal(Object.keys(context.itemAdds).length, 0);
field('editChineseName').value = '测试黄瓜';
context.saveItemEdit({preventDefault(){}});
const added = context.itemAdds['买菜'][0];
assert.equal(added.englishName, '');
assert.equal(added.chineseName, '测试黄瓜');
assert.equal(added.name, '测试黄瓜');
context.editSession.mode = 'edit'; context.editSession.key = added.key;
context.getSourceItems = () => [{...added,photoLookupName:'Original photo name',photo:'saved-photo'}];
context.editSession.photo = 'saved-photo';
field('editName').value = 'Test cucumber'; field('editChineseName').value = '';
context.saveItemEdit({preventDefault(){}});
const saved = JSON.parse(JSON.stringify(context.itemEdits[`买菜::${added.key}`]));
assert.deepEqual(names(saved), {englishName:'Test cucumber',chineseName:''});
assert.equal(saved.photoLookupName, 'Original photo name');
assert.equal(saved.photo, 'saved-photo');
assert.equal(saved.name, 'Test cucumber');
assert.equal(context.pendingEdits[`买菜::${added.key}`].englishName, 'Test cucumber');
console.log('PASS: legacy split, ambiguous preservation, single-language add/edit, blank validation, persisted names and photo identity');
