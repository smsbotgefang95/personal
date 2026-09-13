// Verified product details that were not present in the original AnyList export.
(() => {
  const listName = "橱柜_烹饪用品👩🏻‍🍳";
  const itemName = "Coarse Ground With Parsley Garlic Salt by Lawry's 粗磨香芹蒜盐 (1 × 1罐)";
  const source = window.SMART_LIST_IMPORT?.[listName];

  if (source) {
    const blankRecord = `${itemName}\n\n`;
    const detailedRecord = `${itemName}\n\n💵 $3.22\n⚖️ 6 oz\n🏷️ $0.537 / oz\nWalmart\n`;
    window.SMART_LIST_IMPORT[listName] = source.replaceAll(blankRecord, detailedRecord);
  }

  window.SMART_SHOPPING_NUTRITION?.push({
    collection: listName,
    category: "烹饪_调味品_固体",
    item: itemName,
    basis: "label serving 1/4 tsp (1.1 g)",
    calories: 0,
    protein_g: 0,
    fat_g: 0,
    carbs_g: 0,
    fiber_g: 0,
    sugars_g: 0,
    added_sugars_g: 0,
    sodium_mg: 350,
    source: "Lawry's package label",
    confidence: "matched",
    matched_record: "Lawry's Coarse Ground With Parsley Garlic Salt, 6 oz",
    brand: "Lawry's"
  });
})();

// Verified against the exact 365 by Whole Foods Market Amazon listing on Sep 13, 2026.
(() => {
  const listName = "橱柜_烹饪用品👩🏻‍🍳";
  const itemName = "Baking Soda by 365 苏打 (1 × 1盒)";
  const source = window.SMART_LIST_IMPORT?.[listName];

  if (source) {
    const importedRecord = `${itemName}\n\n⚖️ 16 oz\nAmazon\n`;
    const detailedRecord = `${itemName}\n\n💵 $1.07 / 盒\n⚖️ 16 oz\n🏷️ $0.07 / oz\nAmazon\n`;
    window.SMART_LIST_IMPORT[listName] = source.replaceAll(importedRecord, detailedRecord);
  }
})();

(() => {
  const listName = "橱柜_烹饪用品👩🏻‍🍳";
  const itemName = "Onion Powder by Stonemill 洋葱粉 (1 × 1瓶)";
  const source = window.SMART_LIST_IMPORT?.[listName];

  if (source) {
    const importedRecord = `${itemName}\n\n⚖️ 2.62 oz\nWalmart\n`;
    const detailedRecord = `${itemName}\n\n💵 $5.99\n⚖️ 2.62 oz\n🏷️ $36.58 / lb\nWalmart\n`;
    window.SMART_LIST_IMPORT[listName] = source.replaceAll(importedRecord, detailedRecord);
  }
})();

(() => {
  const listName = "橱柜_烹饪用品👩🏻‍🍳";
  const itemName = "Double Acting Baking Powder by Clabber Girl 双效泡打粉 (1 × 1罐)";
  const source = window.SMART_LIST_IMPORT?.[listName];

  if (source) {
    const importedRecord = `${itemName}\n\n⚖️ 8.1 oz\nAmazon\n`;
    const detailedRecord = `${itemName}\n\n💵 $2.52\n⚖️ 8.1 oz\n🏷️ $0.31 / oz\nAmazon\n`;
    window.SMART_LIST_IMPORT[listName] = source.replaceAll(importedRecord, detailedRecord);
  }
})();
