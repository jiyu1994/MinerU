import os
import json
from magic_pdf.pipe.UNIPipe import UNIPipe
from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter

# =================配置区域=================
# 1. 找一个你的本地 PDF 文件路径 (请确保这个文件存在！)
# 这里默认用了项目自带的 demo 文件，你可以去 demo 文件夹里看看有没有 small_ocr.pdf
pdf_path = r"demo/small_ocr.pdf"  
# 2. 定义输出结果放在哪
output_dir = r"output_result"
# =========================================

def main():
    # 1. 准备工作
    file_name = os.path.basename(pdf_path).split('.')[0]
    
    # 2. 读取 PDF 文件内容
    try:
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {pdf_path}")
        print(f"请检查 'demo' 文件夹里是否有 'small_ocr.pdf'，或者修改代码里的 pdf_path 变量。")
        return

    # 3. 初始化输出写入器
    image_writer = DiskReaderWriter(os.path.join(output_dir, "images"))

    # 4. 初始化管道
    print(f"🚀 开始处理: {file_name} ...")
    # jso_useful_key=None 表示让程序自动探测
    pipe = UNIPipe(pdf_bytes, jso_useful_key=None, image_writer=image_writer)

    # 5. 执行分类
    pipe.pipe_classify()
    print(f"📋 文件类型分类完成")

    # 6. 执行分析 (这一步会加载那 20GB 模型)
    print(f"🧠 开始版面分析 (加载模型中，请稍候)...")
    pipe.pipe_analyze()
    print(f"🧠 版面分析完成")

    # 7. 执行解析与重组
    pipe.pipe_parse()
    print(f"🧩 内容重组完成")

    # 8. 生成 Markdown
    md_content = pipe.pipe_mk_markdown(
        image_dir="images", 
        drop_mode="none"
    )

    # 9. 保存结果
    os.makedirs(output_dir, exist_ok=True)
    out_md_path = os.path.join(output_dir, f"{file_name}.md")
    with open(out_md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    print(f"✅ 处理成功！结果已保存至: {out_md_path}")

if __name__ == "__main__":
    main()