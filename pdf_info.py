import fitz  # pip install pymupdf

def print_pdf_info(pdf_path):
    doc = fitz.open(pdf_path)

    print("="*80)
    print(f"📄 PDF 文件: {pdf_path}")
    print("="*80)

    # —— 文档级信息 ——
    print("\n📌 文档元数据:")
    for k, v in doc.metadata.items():
        print(f"  {k}: {v}")

    print("\n📌 文档权限:")
    perms = doc.permissions
    print(f"  允许打印:      {bool(perms & fitz.PDF_PERM_PRINT)}")
    print(f"  允许修改:      {bool(perms & fitz.PDF_PERM_MODIFY)}")
    print(f"  允许复制:      {bool(perms & fitz.PDF_PERM_COPY)}")
    print(f"  允许注释:      {bool(perms & fitz.PDF_PERM_ANNOTATE)}")

    print(f"\n📌 总页数: {doc.page_count}")

    # —— 每页信息 ——
    for i in range(int(doc.page_count/2)):
        page = doc[i]
        rect = page.rect

        width_pt = rect.width
        height_pt = rect.height
        # 转换单位
        width_mm = width_pt * 25.4 / 72
        height_mm = height_pt * 25.4 / 72

        print("\n" + "-"*40)
        print(f"📄 第 {i + 1} 页")
        print("-"*40)
        print(f"  尺寸（pt）:  {width_pt:.2f} x {height_pt:.2f}")
        print(f"  尺寸（mm）:  {width_mm:.2f} x {height_mm:.2f}")
        print(f"  旋转角度:    {page.rotation}°")

        # 更准确的尺寸：多个 Box
        print("  页面框信息:")
        print(f"    MediaBox: {page.mediabox}")
        print(f"    CropBox:  {page.cropbox}")
        print(f"    TrimBox:  {page.trimbox}")
        print(f"    BleedBox: {page.bleedbox}")
        print(f"    ArtBox:   {page.artbox}")

        # 检查页是否包含文字、图片、表单字段
        text = page.get_text()
        print(f"  文本长度:    {len(text)}")
        print(f"  图片数量:    {len(page.get_images(full=True))}")
        try:
            if callable(page.widgets):
                widgets = page.widgets() or []
            else:
                widgets = page.widgets or []
            print(f"  表单字段数量: {len(widgets)}")
        except Exception:
            print("  表单字段数量: 无法获取")

    doc.close()

# 使用示例
print_pdf_info("input/2025.pdf")