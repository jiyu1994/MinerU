import os
import sys
import threading

from loguru import logger


def run_post_processing(
    output_dir,
    file_name_list,
    method="auto",
    translate_to_english=False,
    translation_api_key=None,
    generate_pdf=False,
    fix_md=False,
    translate_images_api_key=None,
    translate_images=True,
    generate_config=True,
):
    """执行翻译、PDF 生成、Markdown 修复等后处理流程。"""
    # 确保项目根目录在 Python 路径，便于用 post_processing.* 形式导入
    post_processing_path = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(post_processing_path)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        from translate.translate_images import translate_images_for_folder
        from translate.translate import translate_file
        from merge_back.auto_generate_pdf import generate_pdf_from_md_file
        from post_processing.fix_md.fix_md import advanced_fix_markdown
        from post_processing.generate_config.generate_config import analyze_layout
    except ImportError as e:
        logger.error(f"无法导入后处理模块: {e}")
        return

    translate_image_threads = []

    for pdf_file_name in file_name_list:
        parse_method_dir = method if method != "auto" else "auto"
        file_output_dir = os.path.join(output_dir, pdf_file_name, parse_method_dir)
        images_dir = os.path.join(file_output_dir, "images")

        if translate_images and os.path.isdir(images_dir):
            def _translate_images_task(folder=images_dir, pdf=pdf_file_name):
                try:
                    translate_images_for_folder(folder, api_key=translate_images_api_key)
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"图片翻译失败: {pdf}, 错误: {exc}")

            img_thread = threading.Thread(
                target=_translate_images_task,
                name=f"translate_images_{pdf_file_name}",
                daemon=True,
            )
            img_thread.start()
            translate_image_threads.append(img_thread)
            logger.info(f"图片翻译线程已启动（并行）: {pdf_file_name}")
        elif os.path.isdir(images_dir):
            logger.warning(f"未找到图片目录，跳过图片翻译: {images_dir}")
        else:
            logger.info(f"跳过图片翻译（translate_images=False）: {pdf_file_name}")

        original_md_path = os.path.join(file_output_dir, f"{pdf_file_name}.md")
        translated_md_path = os.path.join(file_output_dir, f"{pdf_file_name}_translated.md")

        source_json_path = os.path.join(file_output_dir, f"{pdf_file_name}_content_list.json")
        layout_config_path = os.path.join(file_output_dir, f"{pdf_file_name}_layout_config.json")

        if generate_config:
            logger.info(f"开始生成配置和最终markdown: {pdf_file_name}")
            try:
                middle_md_path = analyze_layout(source_json_path, layout_config_path, original_md_path)
                logger.info(f"配置生成完成: {pdf_file_name}")
            except Exception as e:
                logger.error(f"配置生成失败: {pdf_file_name}, 错误: {e}")
                continue
        else:
            logger.info(f"跳过生成配置（generate_config=False）: {pdf_file_name}")
            middle_md_path = original_md_path

        if translate_to_english:
            if translation_api_key is None:
                logger.error("翻译功能需要提供 translation_api_key")
                continue

            logger.info(f"开始翻译文档: {pdf_file_name}")
            success = translate_file(middle_md_path, translated_md_path, translation_api_key)
            if not success:
                logger.error(f"翻译失败: {pdf_file_name}")
                continue

        if generate_pdf:
            target_md_path = translated_md_path if translate_to_english else original_md_path
            pdf_output_path = os.path.join(file_output_dir, f"{pdf_file_name}_final_paper.pdf")

            logger.info(f"开始生成PDF: {pdf_file_name}")
            success = generate_pdf_from_md_file(target_md_path, pdf_output_path)
            if not success:
                logger.error(f"PDF生成失败: {pdf_file_name}")

        if fix_md:
            # 优先修复翻译后的文件，否则修复原始文件
            target_md_path = translated_md_path if translate_to_english and os.path.exists(translated_md_path) else original_md_path

            logger.info(f"开始修复Markdown文件: {pdf_file_name}")
            try:
                advanced_fix_markdown(target_md_path)
                logger.info(f"Markdown修复完成: {pdf_file_name}")
            except Exception as e:
                logger.error(f"Markdown修复失败: {pdf_file_name}, 错误: {e}")

    for t in translate_image_threads:
        t.join()
    logger.info("所有图片翻译任务已完成")

if __name__ == "__main__":
    # 在此处直接修改配置，避免命令行传参
    OUTPUT_DIR = "output"  # 解析结果输出目录
    FILES = ["2025"]       # 待处理的文件名（不含扩展名）列表
    METHOD = "auto"        # 解析方法目录名
    TRANSLATE = False      # 是否翻译为英文
    TRANSLATION_API_KEY = None  # 翻译 API Key，开启翻译时需要
    GENERATE_PDF = False   # 是否生成最终 PDF
    FIX_MD = False         # 是否修复 Markdown
    TRANSLATE_IMAGES_API_KEY = None  # 图片翻译所用 API Key，默认使用 translate_images.py 中的配置
    TRANSLATE_IMAGES = False           # 是否翻译图片
    GENERATE_CONFIG = True           # 是否生成布局配置

    run_post_processing(
        output_dir=OUTPUT_DIR,
        file_name_list=FILES,
        method=METHOD,
        translate_to_english=TRANSLATE,
        translation_api_key=TRANSLATION_API_KEY,
        generate_pdf=GENERATE_PDF,
        fix_md=FIX_MD,
        translate_images_api_key=TRANSLATE_IMAGES_API_KEY,
        translate_images=TRANSLATE_IMAGES,
        generate_config=GENERATE_CONFIG,
    )