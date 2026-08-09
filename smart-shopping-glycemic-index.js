/* Reference Glycemic Index values used by Smart Shopping. */
window.SMART_SHOPPING_GI = (() => {
  const low = (value, source = "Reference food") => ({ value, label: "Low", status: "low", source });
  const medium = (value, source = "Reference food") => ({ value, label: "Medium", status: "medium", source });
  const high = (value, source = "Reference food") => ({ value, label: "High", status: "high", source });
  const notApplicable = (source = "No meaningful carbohydrate source") => ({ value: null, label: "Not applicable", status: "not-applicable", source });
  const packageLabel = (source = "Product or recipe label needed") => ({ value: null, label: "Package label needed", status: "package-label", source });
  const rules = [
    [/homemade|自制|打卤面卤|梅干菜烧肉|素什锦|馅饼|鸡肉 \(|鸡汤/, packageLabel("Recipe and serving composition needed")],
    [/dumpling|mandu|gyoza|wonton|soup dumpling|汤圆|虾饺|蟹壳黄|灌汤包|饺子|馄饨/, packageLabel()],
    [/sausage|香肠|meatball|榨菜|鱼泉/, packageLabel()],
    [/gravy|marinade|barbecue|bbq|gochujang|dressing|sauce|酱|肉汁|沙拉酱|辣酱/, packageLabel()],
    [/yogurt.*fruit|fruit.*yogurt|酸奶/, packageLabel()],
    [/granola|protein.*bar|chewy bar|wafer|cocoa|chocolate|crisps|crisp|cracker|craisins|dried blueberry|枸杞|红枣|山楂干|梅干菜|果干/, packageLabel()],
    [/crouton|breadcrumb|面包干|意大利面包屑/, high(75)],
    [/sugar|砂糖|黑糖|蔗糖/, medium(65)],
    [/honey|蜂蜜/, medium(58)],
    [/vinegar|醋|soy sauce|酱油|ponzu/, notApplicable("Negligible carbohydrate at a typical serving")],
    [/avocado(?! oil)|牛油果(?!油)/, low(15)],
    [/oil|油(?!面)|芝麻油|紫苏籽油|avocado oil/, notApplicable("No meaningful carbohydrate source")],
    [/salt|盐|pepper|胡椒|baking soda|baking powder|苏打|泡打粉|yeast|酵母|seaweed|海带|紫菜|sea cucumber|海参|白芷/, notApplicable()],
    [/egg|鹌鹑蛋|鸡蛋|cheese|奶酪|chicken|鸡|beef|牛|pork|猪|lamb|羊|duck|鸭|shrimp|虾|salmon|三文鱼|tuna|金枪鱼|tilapia|龙利鱼|mackerel|鲭鱼|branzino|海鲈鱼|cod|鳕鱼|sardine|沙丁鱼|roast chicken|烤鸡/, notApplicable()],
    [/tofu|豆腐|豆皮|素鸡|烤麸|soy bean|soybean|黄豆/, low(15)],
    [/edamame|毛豆/, low(18)],
    [/navy bean|white bean|白芸豆/, low(31)],
    [/black bean|黑豆/, low(30)],
    [/kidney bean|红豆/, low(24)],
    [/chick pea|garbanzo|鹰嘴豆/, low(28)],
    [/fava|蚕豆/, low(48)],
    [/pea|豌豆/, low(48)],
    [/chestnut|栗子/, medium(54)],
    [/almond|peanut|花生|pistachio|开心果|walnut|核桃|chia|奇亚|pumpkin seed|南瓜子|nut butter|坚果/, low(15)],
    [/sweet potato|红薯|purple sweet|紫薯/, medium(61)],
    [/potato|土豆/, high(78)],
    [/taro|芋头/, low(54)],
    [/yam|山药/, low(51)],
    [/cassava|tapioca|木薯|淀粉/, high(70)],
    [/brown rice|糙米/, low(50)],
    [/purple rice|black rice|紫米|黑米/, low(50)],
    [/rice|大米/, high(73)],
    [/glutinous|sticky|糯/, high(75)],
    [/quinoa|藜麦/, low(53)],
    [/millet|小米/, high(70)],
    [/buckwheat|荞麦/, low(49)],
    [/noodle|面条|拉面|油面/, low(55)],
    [/corn meal|玉米粉/, medium(68)],
    [/flour|面粉/, high(70)],
    [/bread|面包/, high(70)],
    [/popcorn|爆米花/, medium(65)],
    [/corn|玉米/, medium(52)],
    [/banana|香蕉/, low(51)],
    [/apple|苹果/, low(36)],
    [/blueberr|蓝莓/, low(53)],
    [/peach|桃/, low(28)],
    [/cherr|樱桃/, low(22)],
    [/lychee|荔枝/, low(50)],
    [/pear|梨/, low(38)],
    [/strawberr|草莓/, low(40)],
    [/carrot|胡萝卜/, low(39)],
    [/green bean|扁豆/, low(32)],
    [/tomato|西红柿|小西红柿/, low(15)],
    [/cucumber|黄瓜/, low(15)],
    [/onion|洋葱|大葱|小葱|韭菜|韭黄/, low(15)],
    [/garlic|蒜|ginger|姜/, low(15)],
    [/mushroom|蘑菇|杏鲍菇|金针菇/, low(10)],
    [/broccoli|西兰花|cabbage|白菜|甘蓝|celery|芹菜|spinach|菠菜|kale|羽衣甘蓝|arugula|芝麻菜|asparagus|芦笋|pepper|彩椒|秋葵|茼蒿|豇豆|丝瓜|竹笋|笋|豆芽|荠菜|菜花|豌豆苗|空心菜|苦菊|上海青|油菜|香菜|rainbow mix/, low(15)],
    [/milk|牛奶/, low(31)],
    [/plain yogurt|triple zero yogurt|yogurt|酸奶/, low(35)]
  ];
  function get(item, nutritionRecord) {
    const name = String(item?.name || "").toLowerCase().replace(/\s+/g, " ").trim();
    const category = String(item?.category || "").toLowerCase().replace(/\s+/g, " ").trim();
    const haystack = `${name} ${category}`;
    for (const [pattern, result] of rules) {
      if (pattern.test(haystack)) return { ...result, confidence: result.status === "package-label" ? "label-dependent" : "reference" };
    }
    if (/meat|fish|seafood|poultry|蛋|奶制品|鱼|虾|鸡|牛|羊|猪|鸭/.test(category)) return { ...notApplicable(), confidence: "category-based" };
    if (Number.isFinite(Number(nutritionRecord?.carbs_g)) && Number(nutritionRecord.carbs_g) <= 1) return { ...notApplicable(), confidence: "nutrition-based" };
    return { ...packageLabel(), confidence: "label-dependent" };
  }
  return { get };
})();
