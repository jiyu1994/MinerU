import os
import sys
import threading
import time
from typing import Optional

import grpc
from loguru import logger


def _load_exporter_modules():
    """
    尝试加载 gRPC 导出服务的 pb2 模块，支持两种导入路径。
    """
    try:
        import exporter_pb2  # type: ignore
        import exporter_pb2_grpc  # type: ignore

        return exporter_pb2, exporter_pb2_grpc
    except ImportError:
        try:
            from post_processing import exporter_pb2, exporter_pb2_grpc  # type: ignore

            return exporter_pb2, exporter_pb2_grpc
        except ImportError as e:
            raise ImportError("未找到 exporter_pb2 / exporter_pb2_grpc，请先根据 proto 生成客户端代码") from e


def export_pdf_via_grpc(md_path: str, config_path: str, target: str, timeout: Optional[int] = 300) -> str:
    """
    通过 gRPC 调用远端服务生成 PDF。
    """
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Markdown 文件不存在: {md_path}")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"布局配置不存在: {config_path}")
    if not target:
        raise ValueError("未提供有效的 gRPC 地址")

    exporter_pb2, exporter_pb2_grpc = _load_exporter_modules()

    request = exporter_pb2.ExportRequest(md_path=md_path, config_path=config_path)
    with grpc.insecure_channel(target) as channel:
        stub = exporter_pb2_grpc.PdfExporterStub(channel)
        response = stub.ExportPdf(request, timeout=timeout)

    if not getattr(response, "pdf_path", None):
        raise RuntimeError("导出服务返回空的 pdf_path")

    return response.pdf_path


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
    pdf_exporter_address=None,
    pdf_export_timeout=300,
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
        from post_processing.fix_md.fix_md_math import advanced_fix_markdown
        from post_processing.generate_config.generate_config import analyze_layout
        from post_processing.header_engine import header_engine
    except ImportError as e:
        logger.error(f"无法导入后处理模块: {e}")
        return

    translate_image_threads = []
    header_futures = {}  # 缓存每个文件的 LLM 代码生成 Future
    pdf_jobs = []  # 延后到所有图片翻译完成后再生成 PDF
    total_start = time.perf_counter()

    for file_idx, pdf_file_name in enumerate(file_name_list, start=1):
        file_start = time.perf_counter()
        parse_method_dir = method if method != "auto" else "auto"
        file_output_dir = os.path.join(output_dir, pdf_file_name, parse_method_dir)
        images_dir = os.path.join(file_output_dir, "images")
        translate_image_thread = None

        if translate_images and os.path.isdir(images_dir):
            def _translate_images_task(folder=images_dir, pdf=pdf_file_name):
                img_start = time.perf_counter()
                try:
                    translate_images_for_folder(folder, api_key=translate_images_api_key)
                    img_cost = time.perf_counter() - img_start
                    logger.info(f"图片翻译完成: {pdf}，耗时 {img_cost:.2f}s")
                except Exception as exc:  # noqa: BLE001
                    img_cost = time.perf_counter() - img_start
                    logger.error(f"图片翻译失败: {pdf}，耗时 {img_cost:.2f}s，错误: {exc}")

            img_thread = threading.Thread(
                target=_translate_images_task,
                name=f"translate_images_{pdf_file_name}",
                daemon=True,
            )
            img_thread.start()
            translate_image_thread = img_thread
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
            config_start = time.perf_counter()
            try:
                middle_md_path = analyze_layout(source_json_path, layout_config_path, original_md_path)
                config_cost = time.perf_counter() - config_start
                logger.info(f"配置生成完成: {pdf_file_name}，耗时 {config_cost:.2f}s")
            except Exception as e:
                config_cost = time.perf_counter() - config_start
                logger.error(f"配置生成失败: {pdf_file_name}，耗时 {config_cost:.2f}s，错误: {e}")
                continue

            # 配置生成完成后立即启动 LLM 代码生成（异步），与后续流程并行
            try:
                header_request_start = time.perf_counter()
                header_futures[pdf_file_name] = header_engine.request_llm_in_background(layout_config_path)
                header_request_cost = time.perf_counter() - header_request_start
                logger.info(f"已启动页眉页脚代码生成（并行）: {pdf_file_name}，耗时 {header_request_cost:.2f}s")
            except Exception as e:
                logger.error(f"启动页眉页脚代码生成失败: {pdf_file_name}, 错误: {e}")
        else:
            logger.info(f"跳过生成配置（generate_config=False）: {pdf_file_name}")
            middle_md_path = original_md_path
            if os.path.exists(layout_config_path):
                try:
                    header_request_start = time.perf_counter()
                    header_futures[pdf_file_name] = header_engine.request_llm_in_background(layout_config_path)
                    header_request_cost = time.perf_counter() - header_request_start
                    logger.info(f"已启动页眉页脚代码生成（并行，复用已有配置）: {pdf_file_name}，耗时 {header_request_cost:.2f}s")
                except Exception as e:
                    logger.error(f"启动页眉页脚代码生成失败: {pdf_file_name}, 错误: {e}")

        if translate_to_english:
            if translation_api_key is None:
                logger.error("翻译功能需要提供 translation_api_key")
                continue

            logger.info(f"开始翻译文档 [{file_idx}/{len(file_name_list)}]: {pdf_file_name}")
            translate_start = time.perf_counter()
            success = translate_file(middle_md_path, translated_md_path, translation_api_key)
            translate_cost = time.perf_counter() - translate_start
            if not success:
                logger.error(f"翻译失败: {pdf_file_name}，耗时 {translate_cost:.2f}s")
                continue
            logger.info(f"翻译完成 [{file_idx}/{len(file_name_list)}]: {pdf_file_name}，耗时 {translate_cost:.2f}s")

        # 统一确定最终用于后续处理/导出的 Markdown 路径
        final_md_path = translated_md_path if translate_to_english and os.path.exists(translated_md_path) else middle_md_path

        if fix_md:
            logger.info(f"开始修复Markdown文件: {pdf_file_name}")
            fix_md_start = time.perf_counter()
            try:
                advanced_fix_markdown(final_md_path)
                # fix_md 会输出 *_fixed.md，这里切换为修复后的文件作为后续输入
                base_dir, base_name = os.path.split(final_md_path)
                name, ext = os.path.splitext(base_name)
                fixed_md_path = os.path.join(base_dir, f"{name}_fixed{ext}")
                logger.info(f"修复后的Markdown文件路径: {fixed_md_path}")
                if os.path.exists(fixed_md_path):
                    final_md_path = fixed_md_path
                    fix_md_cost = time.perf_counter() - fix_md_start
                    logger.info(f"Markdown修复完成并切换输出: {final_md_path}，耗时 {fix_md_cost:.2f}s")
                else:
                    fix_md_cost = time.perf_counter() - fix_md_start
                    logger.warning(f"未找到修复输出文件，继续使用原文件: {final_md_path}，耗时 {fix_md_cost:.2f}s")
            except Exception as e:
                fix_md_cost = time.perf_counter() - fix_md_start
                logger.error(f"Markdown修复失败: {pdf_file_name}，耗时 {fix_md_cost:.2f}s，错误: {e}")

        if generate_pdf:
            pdf_jobs.append(
                {
                    "name": pdf_file_name,
                    "md_path": os.path.abspath(final_md_path),
                    "layout_config": os.path.abspath(layout_config_path),
                }
            )
        file_cost = time.perf_counter() - file_start
        logger.info(f"文件处理耗时 {file_cost:.2f}s: {pdf_file_name}")

    # 统一等待所有图片翻译线程完成，再进行 PDF 导出
    wait_images_start = time.perf_counter()
    for t in translate_image_threads:
        t.join()
    if translate_image_threads:
        wait_images_cost = time.perf_counter() - wait_images_start
        logger.info(f"所有图片翻译任务已完成，等待耗时 {wait_images_cost:.2f}s")

    # 统一执行 PDF 导出及页眉页脚
    for job in pdf_jobs:
        pdf_file_name = job["name"]
        final_md_path = job["md_path"]
        layout_config_path = job["layout_config"]

        pdf_output_path = None
        try:
            pdf_export_start = time.perf_counter()
            pdf_output_path = export_pdf_via_grpc(
                final_md_path,
                layout_config_path,
                target=pdf_exporter_address,
                timeout=pdf_export_timeout,
            )
            pdf_export_cost = time.perf_counter() - pdf_export_start
            logger.info(f"PDF 导出完成: {pdf_output_path}，耗时 {pdf_export_cost:.2f}s")
        except Exception as e:
            pdf_export_cost = time.perf_counter() - pdf_export_start
            logger.error(f"PDF 导出失败: {pdf_file_name}，耗时 {pdf_export_cost:.2f}s，错误: {e}")

        if pdf_output_path:
            future = header_futures.get(pdf_file_name)
            try:
                header_start = time.perf_counter()
                if future:
                    header_output = header_engine.apply_header_when_ready(future, pdf_output_path)
                elif os.path.exists(layout_config_path):
                    header_output = header_engine.run_header_engine(layout_config_path, pdf_output_path)
                else:
                    logger.warning(f"未找到布局配置，跳过页眉页脚: {pdf_file_name}")
                    header_output = None

                if header_output:
                    logger.info(f"页眉页脚处理完成: {header_output}")
                header_cost = time.perf_counter() - header_start
                logger.info(f"页眉页脚耗时 {header_cost:.2f}s: {pdf_file_name}")
            except Exception as e:
                header_cost = time.perf_counter() - header_start
                logger.error(f"页眉页脚处理失败: {pdf_file_name}，耗时 {header_cost:.2f}s，错误: {e}")

    total_cost = time.perf_counter() - total_start
    logger.info(f"后处理流程执行完毕，耗时 {total_cost:.2f}s")

if __name__ == "__main__":
    # 在此处直接修改配置，避免命令行传参
    OUTPUT_DIR = "output"  # 解析结果输出目录
    # FILES = ["2025","H3_AP202001201374385298_1","CAICT","CICC_weekly","CHASING"]       # 待处理的文件名（不含扩展名）列表
    FILES = ["2025"]   
    METHOD = "auto"        # 解析方法目录名
    TRANSLATE = True      # 是否翻译为英文
    TRANSLATION_API_KEY = "apikey-dd675b2a3fcb4f1aa88b91503d87f730"  # 翻译 API Key，开启翻译时需要
    GENERATE_PDF = True   # 是否生成最终 PDF
    FIX_MD = True         # 是否修复 Markdown
    TRANSLATE_IMAGES_API_KEY = "apikey-dd675b2a3fcb4f1aa88b91503d87f730"  # 图片翻译所用 API Key，默认使用 translate_images.py 中的配置
    TRANSLATE_IMAGES = True           # 是否翻译图片
    GENERATE_CONFIG = True           # 是否生成布局配置
    PDF_EXPORTER_ADDRESS = "localhost:50051"  # gRPC 服务地址

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
        pdf_exporter_address=PDF_EXPORTER_ADDRESS,
    )