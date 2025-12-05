import os
import markdown
from playwright.sync_api import sync_playwright

# ================= 配置区域 =================
# 输入和输出文件路径
INPUT_MD = r"../../demo/output/2025/auto/2025_translated.md"
OUTPUT_PDF = r"../../demo/output/2025/auto/2025_final_paper.pdf"
# 学术风 CSS 样式
CSS_STYLE = """
<style>
    body {
        font-family: "Times New Roman", "SimSun", "宋体", serif;
        font-size: 12pt;
        line-height: 1.6;
        color: #333;
        max-width: 21cm;
        margin: 0 auto;
        padding: 2cm;
        background-color: white;
    }
    h1 { text-align: center; font-size: 24pt; margin-bottom: 1em; }
    h2, h3 { border-bottom: 1px solid #eaecef; padding-bottom: .3em; margin-top: 1.5em; }
    /* 改进的图片样式 */
    img {
        display: block;
        margin: 1em auto;
        max-width: 100%;
        height: auto;
        border: 1px solid #eee;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    /* 表格美化 */
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 1.5em 0;
        font-size: 0.9em;
    }
    th, td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }
    th { background-color: #f2f2f2; }
    tr:nth-child(even) { background-color: #f9f9f9; }
    blockquote {
        border-left: 4px solid #42b983;
        padding-left: 1em;
        color: #666;
        background: #f8f8f8;
    }
    /* MathJax样式 */
    .mjx-chtml { font-size: 120%; }
    .mjx-math { font-size: 120%; }
</style>
"""

# MathJax 配置
MATHJAX_SCRIPT = """
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
    processEscapes: true,
    processEnvironments: true,
    packages: {'[+]': ['base', 'ams', 'noerrors', 'noundefined']}
  },
  chtml: {
    fontURL: 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/output/chtml/fonts/woff-v2',
    displayAlign: 'left',
    displayIndent: '2em'
  },
  startup: {
    ready: function() {
      console.log('MathJax is ready');
      MathJax.startup.defaultReady();
    },
    pageReady: function() {
      return MathJax.startup.defaultPageReady();
    }
  }
};
</script>
<script type="text/javascript" id="MathJax-script" async
  src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js">
</script>
<script>
// 确保MathJax在页面加载后重新渲染
document.addEventListener('DOMContentLoaded', function() {
  if (window.MathJax && window.MathJax.typesetPromise) {
    window.MathJax.typesetPromise();
  }
});
</script>
"""
# ===========================================

def md_to_pdf():
    # 1. 检查输入文件
    if not os.path.exists(INPUT_MD):
        print(f"❌ 错误：找不到输入文件 {INPUT_MD}")
        return
    
    # 获取文件所在的目录 (output_result)
    base_dir = os.path.dirname(os.path.abspath(INPUT_MD))

    print("1️⃣  正在将 Markdown 转换为 HTML...")
    with open(INPUT_MD, 'r', encoding='utf-8') as f:
        text = f.read()

    html_body = markdown.markdown(text, extensions=['tables', 'fenced_code'])

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Paper Preview</title>
        {CSS_STYLE}
        {MATHJAX_SCRIPT}
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """

    # 关键修改：把临时 HTML 保存到和 Markdown 同一个文件夹下！
    # 这样 <img src="images/..."> 才能找到相对路径
    temp_html_path = os.path.join(base_dir, "temp_render_preview.html")
    
    with open(temp_html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    print(f"   (临时文件已生成在: {temp_html_path})")

    print("2️⃣  正在启动浏览器引擎进行渲染...")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # 打开这个本地 HTML 文件
        # 注意：必须用绝对路径 file:///
        page.goto(f"file:///{os.path.abspath(temp_html_path)}")
        
        print("⏳ 等待资源加载和公式渲染...")
        # 等待所有网络请求结束（确保图片加载完）
        page.wait_for_load_state("networkidle") 
        # 额外等待 2 秒确保 MathJax 画完公式
        page.wait_for_timeout(2000)

        print(f"3️⃣  正在打印 PDF 到: {OUTPUT_PDF}")
        page.pdf(
            path=OUTPUT_PDF,
            format="A4",
            print_background=True,
            margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"}
        )
        
        browser.close()

    # 清理临时文件 (如果你想看网页版效果，可以注释掉这一行)
    if os.path.exists(temp_html_path):
        os.remove(temp_html_path)


def generate_pdf_from_md_file(input_md_path, output_pdf_path):
    """
    从Markdown文件生成PDF的核心函数
    Args:
        input_md_path: 输入markdown文件路径
        output_pdf_path: 输出PDF文件路径
    Returns:
        bool: PDF生成是否成功
    """
    # 1. 检查输入文件
    if not os.path.exists(input_md_path):
        print(f"❌ 错误：找不到输入文件 {input_md_path}")
        return False

    # 获取文件所在的目录 (output_result)
    base_dir = os.path.dirname(os.path.abspath(input_md_path))

    print("1️⃣  正在将 Markdown 转换为 HTML...")
    with open(input_md_path, 'r', encoding='utf-8') as f:
        text = f.read()

    html_body = markdown.markdown(text, extensions=['tables', 'fenced_code'])

    # 修复HTML中的图片路径：将相对路径转换为绝对路径
    import re

    def fix_image_path_html(match):
        img_src = match.group(1)  # HTML中src属性的值
        if not os.path.isabs(img_src) and not img_src.startswith(('http://', 'https://', 'data:')):
            # 如果是相对路径，转换为相对于base_dir的绝对路径
            abs_path = os.path.join(base_dir, img_src)
            # 在HTML中使用file://协议，并处理Windows路径分隔符
            file_url = f'file:///{abs_path.replace(chr(92), "/")}'  # Windows路径处理
            return f'<img{match.group(2)}src="{file_url}"{match.group(3)}/>'
        return match.group(0)

    # 修复HTML中的图片路径
    html_body = re.sub(r'<img([^>]*?)src="([^"]*?)"([^>]*?)/>', fix_image_path_html, html_body)

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Paper Preview</title>
        {CSS_STYLE}
        {MATHJAX_SCRIPT}
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """

    # 关键修改：把临时 HTML 保存到和 Markdown 同一个文件夹下！
    # 这样 <img src="images/..."> 才能找到相对路径
    temp_html_path = os.path.join(base_dir, "temp_render_preview.html")

    with open(temp_html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    print(f"   (临时文件已生成在: {temp_html_path})")

    # 调试：检查生成的HTML中的图片路径
    with open(temp_html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
        img_matches = re.findall(r'<img[^>]*src="([^"]*)"[^>]*>', html_content)
        if img_matches:
            print(f"   找到 {len(img_matches)} 个图片:")
            for i, img_src in enumerate(img_matches[:3]):  # 只显示前3个
                print(f"     {i+1}. {img_src}")
        else:
            print("   未找到图片标签")

        # 检查MathJax脚本
        if 'MathJax' in html_content:
            print("   MathJax脚本已包含")
        else:
            print("   MathJax脚本缺失")

    print("2️⃣  正在启动浏览器引擎进行渲染...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # 设置视口大小
            page.set_viewport_size({"width": 1200, "height": 800})

            # 打开这个本地 HTML 文件
            # 注意：必须用绝对路径 file:///
            page.goto(f"file:///{os.path.abspath(temp_html_path).replace(chr(92), '/')}")

            print("⏳ 等待资源加载和公式渲染...")

            # 等待页面完全加载
            page.wait_for_load_state("networkidle")

            # 等待MathJax加载和渲染
            print("等待MathJax加载...")
            page.wait_for_timeout(2000)

            # 等待MathJax初始化
            try:
                page.wait_for_function("""
                    () => {
                        return typeof window.MathJax !== 'undefined' && window.MathJax.version;
                    }
                """, timeout=10000)
                print("MathJax已加载，开始渲染公式...")

                # 手动触发MathJax渲染
                page.evaluate("""
                    if (window.MathJax && window.MathJax.typesetPromise) {
                        return window.MathJax.typesetPromise();
                    } else if (window.MathJax && window.MathJax.typeset) {
                        window.MathJax.typeset();
                        return Promise.resolve();
                    }
                """)

                # 等待渲染完成
                page.wait_for_timeout(5000)

                # 检查是否还有未渲染的公式
                unprocessed = page.evaluate("""
                    const mathElements = document.querySelectorAll('.math, [data-tex], .tex');
                    return mathElements.length;
                """)

                if unprocessed > 0:
                    print(f"发现 {unprocessed} 个数学公式，等待额外渲染时间...")
                    page.wait_for_timeout(3000)

                print("公式渲染完成")

            except Exception as e:
                print(f"MathJax渲染等待失败: {e}")
                page.wait_for_timeout(5000)  # 备用等待时间

            print(f"3️⃣  正在打印 PDF 到: {output_pdf_path}")
            page.pdf(
                path=output_pdf_path,
                format="A4",
                print_background=True,
                margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"},
                prefer_css_page_size=True
            )

            browser.close()

        # 清理临时文件 (如果你想看网页版效果，可以注释掉这一行)
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)

        print("✅ PDF生成完成！")
        return True

    except Exception as e:
        print(f"❌ PDF生成出错: {e}")
        # 清理临时文件
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)
        return False


if __name__ == "__main__":
    md_to_pdf()