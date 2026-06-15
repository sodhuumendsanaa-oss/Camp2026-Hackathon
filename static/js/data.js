// ════════════════════════════════════════════════
//  data.js – SQLite API連携（同期通信による在庫・設定管理）
// ════════════════════════════════════════════════

// ── 在庫の取得 ────────────────────────────────────
function getInventory() {
  const xhr = new XMLHttpRequest();
  xhr.open('GET', '/api/inventory', false); // 同期通信
  xhr.send(null);
  if (xhr.status === 200) {
    try {
      return JSON.parse(xhr.responseText);
    } catch (e) {
      console.error("Failed to parse inventory JSON", e);
      return [];
    }
  }
  return [];
}

// ── アイテム追加 ──────────────────────────────────
function addItem(item) {
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/inventory', false); // 同期通信
  xhr.setRequestHeader('Content-Type', 'application/json');
  
  const payload = {
    ...item,
    registeredAt: new Date().toISOString(),
    status: 'fresh'
  };
  
  xhr.send(JSON.stringify(payload));
  if (xhr.status === 200 || xhr.status === 201) {
    try {
      return JSON.parse(xhr.responseText);
    } catch (e) {
      console.error("Failed to parse added item", e);
      return null;
    }
  }
  return null;
}

// ── アイテム削除 ──────────────────────────────────
function deleteItem(id) {
  const xhr = new XMLHttpRequest();
  xhr.open('DELETE', `/api/inventory/${id}`, false); // 同期通信
  xhr.send(null);
  return xhr.status === 200;
}

// ── アイテム更新 ──────────────────────────────────
function updateItem(id, updates) {
  const xhr = new XMLHttpRequest();
  xhr.open('PUT', `/api/inventory/${id}`, false); // 同期通信
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.send(JSON.stringify(updates));
  return xhr.status === 200;
}

// ── 設定の取得 ────────────────────────────────────
function getSettings() {
  const xhr = new XMLHttpRequest();
  xhr.open('GET', '/api/settings', false); // 同期通信
  xhr.send(null);
  if (xhr.status === 200) {
    try {
      const data = JSON.parse(xhr.responseText);
      // 空データの場合のフォールバック
      if (Object.keys(data).length === 0) {
        return {
          fridgeTemp: 4,
          regionTemp: 22,
          location: '東京都',
          lat: 35.6762,
          lon: 139.6503,
          lineUserId: ''
        };
      }
      return data;
    } catch (e) {
      console.error("Failed to parse settings JSON", e);
    }
  }
  return {
    fridgeTemp: 4,
    regionTemp: 22,
    location: '東京都',
    lat: 35.6762,
    lon: 139.6503,
    lineUserId: ''
  };
}

// ── 設定の保存 ────────────────────────────────────
function saveSettings(settings) {
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/settings', false); // 同期通信
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.send(JSON.stringify(settings));
  return xhr.status === 200;
}

// ── カテゴリの日本語名 ────────────────────────────
const CATEGORY_LABELS = {
  meat:      '🥩 肉類',
  fish:      '🐟 魚介',
  vegetable: '🥦 野菜',
  fruit:     '🍎 果物',
  dairy:     '🥛 乳製品',
  beverage:  '🧃 飲み物',
  snack:     '🍪 スナック',
  grain:     '🌾 穀物',
  condiment: '🧂 調味料',
  other:     '📦 その他'
};

// ── 保存場所の日本語名 ────────────────────────────
const STORAGE_LABELS = {
  fridge:  '❄️ 冷蔵',
  freezer: '🧊 冷凍',
  room:    '🏠 常温'
};

// ── ステータスの日本語名 ──────────────────────────
const STATUS_LABELS = {
  fresh:    '✅ 良好',
  warning:  '⚠️ 注意',
  danger:   '🚨 危険',
  consumed: '✔️ 消費済'
};
