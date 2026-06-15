// ════════════════════════════════════════════════════
//  shelflife.js – 食材の標準保存日数データベース
//  温度補正（Q10則）で実際の日数を計算する
// ════════════════════════════════════════════════════

/**
 * 食材データベース
 * room: 常温での標準日数
 * fridge: 冷蔵での標準日数
 * freezer: 冷凍での標準日数
 * baseRoomTemp: 常温の基準温度 (°C)
 * baseFridgeTemp: 冷蔵の基準温度 (°C)
 * defaultStorage: デフォルト保存方法
 * category: カテゴリ
 */
const SHELF_LIFE_DB = [
  // ── 野菜 ─────────────────────────────────────
  { keywords: ['じゃがいも', 'ジャガイモ', 'じゃが芋', 'potato'],   room: 30,  fridge: 90,  freezer: 365, baseRoomTemp: 15, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'vegetable' },
  { keywords: ['にんじん', 'ニンジン', '人参', 'carrot'],           room: 10,  fridge: 30,  freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['たまねぎ', '玉ねぎ', 'タマネギ', 'onion'],          room: 60,  fridge: 90,  freezer: 365, baseRoomTemp: 15, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'vegetable' },
  { keywords: ['キャベツ', 'cabbage', 'かべつ'],                     room: 14,  fridge: 21,  freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['ほうれんそう', 'ほうれん草', 'spinach'],             room: 2,   fridge: 5,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['レタス', 'lettuce'],                                  room: 3,   fridge: 7,   freezer: null,baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['トマト', 'tomato'],                                   room: 7,   fridge: 14,  freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'vegetable' },
  { keywords: ['きゅうり', 'キュウリ', '胡瓜', 'cucumber'],         room: 3,   fridge: 7,   freezer: null,baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['なす', 'ナス', '茄子', 'eggplant'],                  room: 3,   fridge: 7,   freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['ピーマン', 'pepper', 'bell pepper'],                  room: 5,   fridge: 10,  freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['ブロッコリー', 'broccoli'],                           room: 3,   fridge: 7,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['もやし', 'bean sprout'],                              room: 1,   fridge: 3,   freezer: null,baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['ねぎ', 'ネギ', '長ネギ', '長ねぎ', 'scallion'],     room: 5,   fridge: 14,  freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['しょうが', '生姜', 'ショウガ', 'ginger'],            room: 14,  fridge: 30,  freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'vegetable' },
  { keywords: ['にんにく', 'ニンニク', '大蒜', 'garlic'],            room: 30,  fridge: 60,  freezer: 365, baseRoomTemp: 15, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'vegetable' },
  { keywords: ['かぼちゃ', 'カボチャ', '南瓜', 'pumpkin'],           room: 30,  fridge: 60,  freezer: 365, baseRoomTemp: 15, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'vegetable' },
  { keywords: ['さつまいも', 'サツマイモ', '薩摩芋', 'sweet potato'], room: 30,  fridge: null, freezer: 365, baseRoomTemp: 15, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'vegetable' },
  { keywords: ['大根', 'だいこん', 'ダイコン', 'radish'],             room: 7,   fridge: 14,  freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },
  { keywords: ['白菜', 'はくさい', 'ハクサイ', 'napa'],               room: 7,   fridge: 14,  freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'vegetable' },

  // ── 果物 ─────────────────────────────────────
  { keywords: ['バナナ', 'banana'],                                   room: 5,   fridge: 7,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'fruit' },
  { keywords: ['りんご', 'リンゴ', '林檎', 'apple'],                  room: 7,   fridge: 30,  freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'fruit' },
  { keywords: ['みかん', 'ミカン', '蜜柑', 'orange', 'mandarin'],     room: 14,  fridge: 30,  freezer: null,baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'fruit' },
  { keywords: ['いちご', 'イチゴ', '苺', 'strawberry'],               room: 2,   fridge: 5,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'fruit' },
  { keywords: ['ぶどう', 'ブドウ', '葡萄', 'grape'],                  room: 3,   fridge: 7,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'fruit' },
  { keywords: ['もも', '桃', 'peach'],                                room: 3,   fridge: 5,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'fruit' },

  // ── 肉類 ─────────────────────────────────────
  { keywords: ['牛肉', 'ぎゅうにく', 'beef'],                         room: 0,   fridge: 3,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'meat' },
  { keywords: ['豚肉', 'ぶたにく', 'pork'],                           room: 0,   fridge: 2,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'meat' },
  { keywords: ['鶏肉', 'とりにく', 'chicken'],                        room: 0,   fridge: 2,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'meat' },
  { keywords: ['ひき肉', '挽き肉', '挽肉', 'ground meat'],           room: 0,   fridge: 1,   freezer: 14,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'meat' },
  { keywords: ['ベーコン', 'bacon'],                                   room: 0,   fridge: 7,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'meat' },
  { keywords: ['ハム', 'ham'],                                         room: 0,   fridge: 5,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'meat' },
  { keywords: ['ソーセージ', 'sausage'],                               room: 0,   fridge: 5,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'meat' },

  // ── 魚介 ─────────────────────────────────────
  { keywords: ['鮭', 'さけ', 'サーモン', 'salmon'],                   room: 0,   fridge: 2,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'fish' },
  { keywords: ['まぐろ', 'マグロ', '鮪', 'tuna'],                     room: 0,   fridge: 1,   freezer: 14,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'fish' },
  { keywords: ['えび', 'エビ', '海老', 'shrimp'],                     room: 0,   fridge: 2,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'fish' },
  { keywords: ['いか', 'イカ', '烏賊', 'squid'],                      room: 0,   fridge: 1,   freezer: 14,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'fish' },

  // ── 乳製品 ───────────────────────────────────
  { keywords: ['牛乳', 'ぎゅうにゅう', 'milk'],                       room: 0,   fridge: 7,   freezer: null,baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'dairy' },
  { keywords: ['ヨーグルト', 'yogurt', 'ヨーグルト'],                  room: 0,   fridge: 14,  freezer: null,baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'dairy' },
  { keywords: ['バター', 'butter'],                                    room: 0,   fridge: 30,  freezer: 180, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'dairy' },
  { keywords: ['チーズ', 'cheese'],                                    room: 0,   fridge: 21,  freezer: 90,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'dairy' },
  { keywords: ['豆腐', 'とうふ', 'tofu'],                             room: 0,   fridge: 4,   freezer: null,baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'other' },
  { keywords: ['卵', 'たまご', 'タマゴ', 'egg'],                      room: 7,   fridge: 28,  freezer: null,baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'fridge', category: 'dairy' },

  // ── 穀物・その他 ─────────────────────────────
  { keywords: ['米', 'こめ', 'お米', 'rice'],                         room: 60,  fridge: 90,  freezer: null,baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'grain' },
  { keywords: ['パン', 'bread'],                                       room: 4,   fridge: 7,   freezer: 30,  baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'grain' },
  { keywords: ['豆', '大豆', 'bean'],                                  room: 180, fridge: 365, freezer: 365, baseRoomTemp: 20, baseFridgeTemp: 4, defaultStorage: 'room',   category: 'grain' },
];

/**
 * 食材名からデータベースを検索する（部分一致）
 */
function findShelfLife(foodName) {
  const name = foodName.toLowerCase().trim();
  return SHELF_LIFE_DB.find(item =>
    item.keywords.some(kw => name.includes(kw.toLowerCase()) || kw.toLowerCase().includes(name))
  ) || null;
}

/**
 * 温度補正で実際の保存可能日数を計算する
 * @param {number} baseDays     標準保存日数
 * @param {number} actualTemp   実際の温度 (°C)
 * @param {number} baseTemp     基準温度 (°C)
 * @param {number} q10          Q10係数（デフォルト2.0）
 * @returns {number}            実際の保存可能日数（四捨五入）
 */
function adjustDaysByTemperature(baseDays, actualTemp, baseTemp, q10 = 2.0) {
  const accelerationRate = Math.pow(q10, (actualTemp - baseTemp) / 10);
  return Math.round(baseDays / accelerationRate);
}

/**
 * 食材名と保存方法から推定期限日を計算する
 * @param {string} foodName     食材名
 * @param {string} storageType  保存方法 ('room'|'fridge'|'freezer')
 * @param {Object} settings     温度設定
 * @returns {Object|null}       { date, days, found, source } または null
 */
function estimateExpiryDate(foodName, storageType, settings) {
  const entry = findShelfLife(foodName);

  let baseDays, actualTemp, baseTemp;

  if (entry) {
    // ── データベースで見つかった ──────────────────
    baseDays = entry[storageType];
    if (!baseDays || baseDays === 0) {
      // その保存方法が非推奨の場合、別の保存方法を提案
      if (storageType === 'room' && entry.fridge) {
        return { found: true, source: 'db', error: `「${foodName}」は常温保存非推奨です。冷蔵推奨: 約${entry.fridge}日。` };
      }
      return null;
    }

    if (storageType === 'fridge') {
      actualTemp = settings.fridgeTemp ?? 4;
      baseTemp   = entry.baseFridgeTemp ?? 4;
    } else if (storageType === 'freezer') {
      // 冷凍はほぼ劣化しないので補正なし
      actualTemp = -18;
      baseTemp   = -18;
    } else {
      actualTemp = settings.regionTemp ?? 20;
      baseTemp   = entry.baseRoomTemp ?? 20;
    }

    const adjustedDays = adjustDaysByTemperature(baseDays, actualTemp, baseTemp);
    const expiryDate   = new Date();
    expiryDate.setDate(expiryDate.getDate() + adjustedDays);
    const dateStr = expiryDate.toISOString().split('T')[0];

    return {
      found:       true,
      source:      'db',
      days:        adjustedDays,
      date:        dateStr,
      baseDays:    baseDays,
      actualTemp:  actualTemp,
      category:    entry.category,
      defaultStorage: entry.defaultStorage
    };
  }

  // ── データベースにない → null を返す（APIに委ねる） ──
  return null;
}
