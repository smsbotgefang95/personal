// Verified product details that were not present in the original AnyList export.
(() => {
  const listName = "橱柜_烹饪用品👩🏻‍🍳";
  const itemName = "Coarse Ground With Parsley Garlic Salt by Lawry's 粗磨香芹蒜盐 (1 × 1罐)";
  const source = window.SMART_LIST_IMPORT?.[listName];

  if (source) {
    const blankRecord = `${itemName}\n\n`;
    const detailedRecord = `${itemName}\n\n💵 $9.78 [⬇️ $2.30 off]\n⚖️ 33 oz\n🏷️ $4.74 / lb [⬇️ $3.63 / lb]\nCostco\n`;
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
    source: "Costco supplier label",
    confidence: "matched",
    matched_record: "Lawry's Coarse Ground Garlic Salt with Parsley, 33 oz",
    brand: "Lawry's"
  });
})();
