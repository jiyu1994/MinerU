// test_load.js
try {
    const { Notebook } = require('crossnote');
    console.log("✅ Crossnote 库加载成功！");
  } catch (e) {
    console.error("❌ 加载失败:", e);
  }