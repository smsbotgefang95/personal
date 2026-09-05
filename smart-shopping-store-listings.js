// Manually researched public listings. Prices are snapshots, not live local quotes.
window.SMART_SHOPPING_STORE_LISTINGS = [{
  itemName: "Free range organic grade A medium egg 有机鸡蛋",
  product: "Contented Hen Organic Free Range Grade A Medium Eggs",
  identityNote: "Brand, organic/free-range type, and medium size matched to your saved carton photo. Your carton contains 24 eggs (UPC 853730007098). Grocery Outlet has an 18-egg package of the same variety.",
  checkedOn: "2026-09-05",
  location: "Shopping area: 20871 · delivery eligibility not confirmed",
  baseline: { price: 7.69, count: 24, label: "Saved Costco reference · date unknown", traits: "Contented Hen · organic · free-range · medium · 24 eggs" },
  alternatives: [
    {
      product: "Kirkland Signature Free-Range Organic Large Eggs",
      store: "Costco", count: 24, price: 9.41,
      priceContext: "Same-Day online snapshot; warehouse price and stock need checking",
      traits: "Organic · free-range · large · 24 eggs",
      reason: "Worth checking on your usual Costco trip if you prefer large eggs. Keeps the organic and free-range attributes of your current eggs.",
      tradeoff: "Different brand and larger eggs. The online quote does not establish what you would pay in the warehouse.",
      url: "https://sameday.costco.com/store/costco/products/19232685-kirkland-signature-organic-free-range-egg-usda-grade-a-lg-24-ct-24-ct",
      evidenceUrl: "https://sameday.costco.com/store/costco/products/19232685-kirkland-signature-organic-free-range-egg-usda-grade-a-lg-24-ct-24-ct",
      evidenceLabel: "Costco product details"
    },
    {
      product: "Vital Farms Organic Pasture-Raised Large Eggs",
      store: "Target", count: 12, price: 6.99,
      priceContext: "Public online sale snapshot (regular $8.69); local price, sale end and stock unconfirmed",
      traits: "Organic · pasture-raised · large · 12 eggs · Certified Humane",
      reason: "Worth considering if pasture access is a priority. Vital Farms states at least 108 square feet of pasture per hen.",
      tradeoff: "Different brand, larger eggs and a smaller carton. Costs more at the observed price; check a store already on your route before making an extra trip.",
      url: "https://www.target.com/p/-/A-52235226",
      evidenceUrl: "https://vitalfarms.com/organic-pasture-raised-eggs/",
      evidenceLabel: "Producer's farming practices"
    }
  ],
  listings: [
    {
      store: "Costco", channel: "Same-Day delivery · indexed price", count: 24, price: 6.80,
      availability: "Out of stock in browser; 20871 quote not confirmed",
      url: "https://sameday.costco.com/store/costco/products/50000333-contented-hen-grade-a-organic-free-range-eggs-24-ct"
    },
    {
      store: "Grocery Outlet", channel: "Online delivery · indexed price", count: 18, price: 12.99,
      availability: "Unavailable in browser; 20871 delivery not confirmed",
      url: "https://shop.groceryoutlet.com/store/grocery-outlet/products/17978848-contented-hen-medium-organic-eggs-18-ct"
    },
    {
      store: "Papaya Express", channel: "Online store · Detroit, MI", count: 24, price: 4.99,
      availability: "Listed for sale; shipping to 20871 unconfirmed",
      url: "https://papayaexpress.com/products/contented-hen-free-range-organic-eggs-24-ct"
    }
  ]
}];
