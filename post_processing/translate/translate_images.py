import os
import time
import shutil
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from loguru import logger

# ================= 配置区域 =================
API_KEY = "apikey-dd675b2a3fcb4f1aa88b91503d87f730"
TARGET_FOLDER = "output/H3_AP202001201374385298_1/auto/images"
PROMPT_TEXT = "Translate other languages in the image to English"

# 并发数量
MAX_WORKERS = 20
# ===========================================

def get_image_info(image_path):
    """
    获取原图的精确信息：宽、高、原始格式
    """
    try:
        with Image.open(image_path) as img:
            return {
                "width": img.width,
                "height": img.height,
                "format": img.format, # 如 'JPEG', 'PNG'
                "mode": img.mode      # 如 'RGB', 'RGBA'
            }
    except Exception as e:
        logger.exception(f"读取图片信息失败: {image_path}, 错误: {e}")
        return None

def get_safe_dimensions(w, h):
    """
    根据原宽高，计算出符合 API 要求的 64 倍数宽高
    """
    safe_w = w
    safe_h = h
    safe_w = max(512, safe_w) # 最小保底
    safe_h = max(512, safe_h)
    return safe_w, safe_h

def post_process_image(downloaded_path, final_save_path, original_info):
    """
    【关键步骤】
    将下载下来的 AI 图片：
    1. 缩放回原始尺寸 (像素级一致)
    2. 转换回原始格式 (JPG/PNG)
    3. 压缩体积
    """
    try:
        with Image.open(downloaded_path) as img:
            # 1. 强制缩放回原图尺寸
            # 使用 LANCZOS 滤镜保证缩放质量
            img_resized = img.resize((original_info["width"], original_info["height"]), Image.Resampling.LANCZOS)
            
            # 2. 准备保存参数
            save_kwargs = {}
            original_format = original_info["format"] or "JPEG" # 默认 JPEG
            
            # 如果原图是 JPEG，启用压缩优化
            if original_format.upper() in ["JPEG", "JPG"]:
                save_kwargs["quality"] = 85      # 质量 1-100，85 是平衡点，既清晰又小
                save_kwargs["optimize"] = True   # 开启额外压缩算法
                # 确保模式是 RGB，因为 JPEG 不支持透明通道 RGBA
                if img_resized.mode == "RGBA":
                    img_resized = img_resized.convert("RGB")
            
            # 3. 覆盖保存
            img_resized.save(final_save_path, format=original_format, **save_kwargs)
            return True
            
    except Exception as e:
        logger.exception(
            "后处理（还原尺寸/格式）失败",
            downloaded_path=downloaded_path,
            final_save_path=final_save_path,
            original_info=original_info,
            error=e,
        )
        return False

def upload_temp_image(file_path, filename_tag):
    url = "https://tmpfiles.org/api/v1/upload"
    logger.info(f"[{filename_tag}] 上传临时文件开始: {file_path}")
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(url, files={'file': f}, headers={'Connection': 'close'}, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            temp_url = data['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
            logger.info(f"[{filename_tag}] 上传成功，临时地址: {temp_url}")
            return temp_url
        else:
            logger.error(
                f"[{filename_tag}] 上传失败",
                status_code=response.status_code,
                text=response.text,
            )
    except Exception as e:
        logger.exception(f"[{filename_tag}] 上传临时文件异常: {e}", file_path=file_path)
    return None

def process_with_ai(image_url, safe_w, safe_h, filename_tag, api_key, prompt_text):
    generate_url = "https://api.atlascloud.ai/api/v1/model/generateImage"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Connection": "close",
    }

    data = {
        "model": "atlascloud/qwen-image/edit-plus",
        "enable_base64_output": False,
        "enable_sync_mode": False,
        "images": [image_url],
        # 即使我们要 JPG，中间过程也建议请求 PNG，避免反复压缩导致画质劣化
        # 我们最后会在本地转回 JPG
        "output_format": "png", 
        "prompt": prompt_text,
        "width": safe_w,
        "height": safe_h
    }

    logger.info(
        f"[{filename_tag}] AI 请求开始",
        image_url=image_url,
        safe_w=safe_w,
        safe_h=safe_h,
        prompt=prompt_text,
    )

    try:
        resp = requests.post(generate_url, headers=headers, json=data, timeout=30)
        if resp.status_code != 200:
            logger.error(
                f"[{filename_tag}] 触发生成失败",
                status_code=resp.status_code,
                text=resp.text,
            )
            return None

        res_json = resp.json()
        if "data" not in res_json:
            logger.error(f"[{filename_tag}] 生成响应缺少 data 字段", response=res_json)
            return None
        
        pred_id = res_json["data"]["id"]
        poll_url = f"https://api.atlascloud.ai/api/v1/model/prediction/{pred_id}"
        logger.info(f"[{filename_tag}] 进入轮询: {poll_url}")
        
        while True:
            try:
                poll_resp = requests.get(
                    poll_url,
                    headers={"Authorization": f"Bearer {api_key}", "Connection": "close"},
                    timeout=30,
                )
                poll_json = poll_resp.json()
                status = poll_json["data"]["status"]
                
                if status == "completed":
                    output_url = poll_json["data"]["outputs"][0]
                    logger.info(f"[{filename_tag}] 轮询完成，输出: {output_url}")
                    return output_url
                elif status == "failed":
                    logger.error(f"[{filename_tag}] 轮询失败", response=poll_json)
                    return None
                time.sleep(2)
            except Exception as e:
                logger.warning(f"[{filename_tag}] 轮询异常，重试: {e}")
                time.sleep(2)
    except Exception as e:
        logger.exception(f"[{filename_tag}] AI 处理异常: {e}")
        return None

def download_temp(url, save_path):
    """下载到临时文件"""
    logger.info(f"下载生成结果: {url} -> {save_path}")
    try:
        response = requests.get(url, stream=True, headers={'Connection': 'close'}, timeout=60)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
        else:
            logger.error("下载生成结果失败", status_code=response.status_code, text=response.text, url=url)
    except Exception as e:
        logger.exception(f"下载生成结果异常: {e}", url=url, save_path=save_path)
    return False

def worker_task(filename, source_folder, target_folder, api_key, prompt_text):
    source_path = os.path.join(source_folder, filename)
    target_path = os.path.join(target_folder, filename)
    
    # 临时下载路径 (为了不直接覆盖目标，方便做后处理)
    temp_download_path = os.path.join(target_folder, f"temp_{filename}")

    supported_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    if not filename.lower().endswith(supported_extensions):
        shutil.copy2(source_path, target_path)
        logger.info(f"[{filename}] 非图片文件，直接复制。")
        return

    logger.info(f"[{filename}] 🚀 开始处理...")

    # 1. 获取原图所有信息
    original_info = get_image_info(source_path)
    if not original_info:
        shutil.copy2(source_path, target_path)
        logger.error(f"[{filename}] 获取原图信息失败，已保留原图。")
        return

    # 2. 计算 AI 需要的“凑整”尺寸
    safe_w, safe_h = get_safe_dimensions(original_info['width'], original_info['height'])

    # 3. 核心流程
    success = False
    fail_reason = None
    temp_url = upload_temp_image(source_path, filename)
    
    if temp_url:
        ai_result_url = process_with_ai(
            temp_url,
            safe_w,
            safe_h,
            filename,
            api_key,
            prompt_text,
        )
        if ai_result_url:
            # 先下载到临时文件 (格式可能是 PNG，尺寸是不对的)
            if download_temp(ai_result_url, temp_download_path):
                # 4. 【关键】执行本地还原操作
                # 把 temp 文件读取，缩放回原尺寸，转回原格式，覆盖保存到 target_path
                if post_process_image(temp_download_path, target_path, original_info):
                    success = True
                    logger.info(f"[{filename}] ✅ 处理完成 (尺寸/格式已还原)")
                else:
                    fail_reason = "后处理失败"
            else:
                fail_reason = "下载结果失败"
        else:
            fail_reason = "AI 生成失败"
    else:
        fail_reason = "上传临时文件失败"

    # 清理临时下载文件
    if os.path.exists(temp_download_path):
        os.remove(temp_download_path)

    # 5. 失败保底
    if not success:
        logger.error(f"[{filename}] ⚠️ 失败，保留原图。原因: {fail_reason}")
        shutil.copy2(source_path, target_path)

def translate_images_for_folder(target_folder, api_key=None, prompt_text=None, max_workers=MAX_WORKERS):
    """
    翻译指定文件夹中的图片。会备份原图并并发处理。
    """
    api_key = api_key or API_KEY
    prompt_text = prompt_text or PROMPT_TEXT

    if not os.path.exists(target_folder):
        logger.error(f"错误：找不到文件夹 '{target_folder}'")
        return

    timestamp = int(time.time())
    backup_folder = f"{target_folder}_original_{timestamp}"
    
    try:
        logger.info(f"开始图片翻译，目标目录: {target_folder}, 备份目录: {backup_folder}")
        os.rename(target_folder, backup_folder)
        os.makedirs(target_folder)
        logger.info(f"=== 原图已备份至: {backup_folder} ===")
    except Exception as e:
        logger.exception(f"初始化失败: {e}", target_folder=target_folder, backup_folder=backup_folder)
        return

    all_files = [f for f in os.listdir(backup_folder) if os.path.isfile(os.path.join(backup_folder, f))]
    logger.info(f"开始处理 {len(all_files)} 个文件 (并发数: {max_workers})...\n")

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                worker_task,
                f,
                backup_folder,
                target_folder,
                api_key,
                prompt_text,
            )
            for f in all_files
        ]
        for future in as_completed(futures):
            pass

    logger.info("图片翻译任务全部完成")
    return True


def main():
    translate_images_for_folder(TARGET_FOLDER, api_key=API_KEY, prompt_text=PROMPT_TEXT, max_workers=MAX_WORKERS)

if __name__ == "__main__":
    main()