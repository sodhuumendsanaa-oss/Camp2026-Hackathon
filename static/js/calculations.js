// ════════════════════════════════════════════════
//  calculations.js – Q10則による食品劣化計算
// ════════════════════════════════════════════════

/**
 * Q10則で劣化加速率を計算する
 * @param {number} currentTemp  現在の温度 (°C)
 * @param {number} baseTemp     基準温度 (°C)
 * @param {number} q10          Q10係数（通常 2.0）
 * @returns {number}            加速率（1.0 = 基準、2.0 = 2倍速く劣化）
 */
function calculateAccelerationRate(currentTemp, baseTemp = 10, q10 = 2.0) {
  return Math.pow(q10, (currentTemp - baseTemp) / 10);
}

/**
 * 食材の劣化情報を計算する
 * @param {Object} item       食材オブジェクト
 * @param {Object} settings   温度設定
 * @returns {Object}          劣化情報
 */
function calculateDeterioration(item, settings) {
  const now          = new Date();
  const expiryDate   = new Date(item.expiryDate);
  const registeredAt = new Date(item.registeredAt);

  // 単純な残り日数（表示用）
  const displayDaysLeft = Math.floor((expiryDate - now) / (1000 * 60 * 60 * 24));

  // 登録日から期限までの合計日数
  const totalDays = Math.max(0, Math.floor((expiryDate - registeredAt) / (1000 * 60 * 60 * 24)));

  // 保存方法に応じた温度を決定
  let currentTemp, baseTemp;
  if (item.storageType === 'fridge') {
    currentTemp = settings.fridgeTemp ?? 4;
    baseTemp    = 10; // 要冷蔵の基準温度
  } else if (item.storageType === 'freezer') {
    currentTemp = -18;
    baseTemp    = -18; // 冷凍は劣化ほぼなし
  } else {
    // room temperature
    currentTemp = settings.regionTemp ?? 25;
    baseTemp    = 25; // 常温の基準温度
  }

  // 劣化加速率
  const accelerationRate = calculateAccelerationRate(currentTemp, baseTemp);

  // 登録からの経過日数
  const daysPassed = Math.max(0, Math.floor((now - registeredAt) / (1000 * 60 * 60 * 24)));

  // 温度加速を考慮した実効経過日数
  const effectiveDaysPassed = daysPassed * accelerationRate;

  // 実効残存日数
  const effectiveDaysLeft = Math.max(0, totalDays - effectiveDaysPassed);

  // ステータス判定
  let status = 'fresh';
  if (displayDaysLeft < 0) {
    status = 'danger';              // 期限切れ
  } else if (effectiveDaysLeft <= 1 || displayDaysLeft === 0) {
    status = 'danger';              // 今日中 / 実効1日以内
  } else if (effectiveDaysLeft <= 3 || displayDaysLeft <= 3) {
    status = 'warning';             // 残り3日以内
  }

  return {
    accelerationRate,
    effectiveDaysLeft,
    displayDaysLeft,
    status,
    temperature: currentTemp
  };
}

/**
 * 在庫リスト全体にステータスを計算して付与する
 * @param {Array}  items    食材リスト
 * @param {Object} settings 温度設定
 * @returns {Array}         ステータス付き食材リスト
 */
function processInventory(items, settings) {
  return items.map(item => {
    const calc = calculateDeterioration(item, settings);
    return {
      ...item,
      status:           calc.status,
      effectiveDaysLeft: calc.effectiveDaysLeft,
      displayDaysLeft:   calc.displayDaysLeft
    };
  });
}
