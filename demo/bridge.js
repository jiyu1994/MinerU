// bridge.js
const { Notebook } = require('crossnote');
const path = require('path');
const fs = require('fs');

// --- 关键配置：手动指定 Windows Chrome 路径 ---
// 如果脚本报错找不到 Chrome，请取消下面某一行的注释，确保指向你电脑上真实的 chrome.exe
const WINDOWS_CHROME_PATHS = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  // 'D:\\你的软件安装目录\\Chrome\\Application\\chrome.exe' 
];

// 自动寻找存在的路径
const chromePath = WINDOWS_CHROME_PATHS.find(p => fs.existsSync(p)) || '';

async function convertToPdf(filePath) {
  // 处理 Windows 路径分隔符
  const absFilePath = path.resolve(filePath); 
  const notebookPath = path.dirname(absFilePath);
  const fileName = path.basename(absFilePath);

  console.log(`[Node] 目标文件: ${fileName}`);
  if (chromePath) {
    console.log(`[Node] 使用 Chrome 路径: ${chromePath}`);
  } else {
    console.log(`[Node] 未找到本地 Chrome，尝试使用 Puppeteer 内置版本...`);
  }

  try {
    const notebook = await Notebook.init({
      notebookPath: notebookPath,
      config: {
        previewTheme: 'github-light.css', 
        mathRenderingOption: 'KaTeX',
        // 关键：传入找到的 Chrome 路径
        chromePath: chromePath, 
      },
    });

    const engine = notebook.getNoteMarkdownEngine(fileName);

    console.log('[Node] 正在渲染并导出 PDF...');
    
    // Windows 下 PDF 生成有时候比较慢，耐心等待
    await engine.chromeExport({ 
      fileType: 'pdf', 
      runAllCodeChunks: true,
      openFileAfterGeneration: false 
    });

    console.log(`[Node] 成功! PDF 已生成.`);
    process.exit(0);
  } catch (error) {
    console.error("[Node] 错误:", error);
    process.exit(1);
  }
}

const targetFile = process.argv[2];
if (!targetFile) {
  console.error("请传入文件路径");
  process.exit(1);
}

convertToPdf(targetFile);