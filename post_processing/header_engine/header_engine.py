
# --- 配置部分 ---
API_KEY = "apikey-dd675b2a3fcb4f1aa88b91503d87f730"


# 文件路径配置
INPUT_JSON_PATH = r"D:\job\atlascloud\MinerU\output\CAICT\auto\CAICT_layout_config.json"      # 你的原始 JSON 文件
INPUT_PDF_PATH = r"D:\job\atlascloud\MinerU\output\CAICT\auto\CAICT_translated_v2_2025-12-10_08-09-52.pdf"         # 你的输入 PDF
OUTPUT_PDF_PATH = r"D:\job\atlascloud\MinerU\output\CAICT\auto\CAICT_final_paper_styled1210.pdf"      # 你的输出 PDF

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
import fitz  # PyMuPDF
from openai import OpenAI

# --- Configuration ---
BASE_URL = "https://api.atlascloud.ai/v1"
MODEL = "google/gemini-3-pro-preview"

# 初始化 OpenAI 客户端
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
_executor = ThreadPoolExecutor(max_workers=2)


def load_header_candidates(json_path):
    """读取 JSON 文件并提取 header_candidates 属性"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 兼容处理：获取 header_candidates 或直接使用数据
            if isinstance(data, dict) and "header_candidates" in data:
                return json.dumps(data["header_candidates"], ensure_ascii=False)
            else:
                return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        print(f"❌ 读取 JSON 失败: {e}")
        return None

def generate_code_from_llm(json_data_string):
    """调用大模型生成处理函数 (使用 OpenAI 客户端)"""
    print("🤖 正在请求 LLM 生成代码...")
    
    # 组装 Prompt (保持之前的逻辑，强制要求生成函数)
    prompt_content = f"""
Role: You are an expert Python Developer specialized in PDF processing with PyMuPDF (fitz).

Task:
I have a translated.pdf and a raw JSON dataset containing header/footer layout information from the original document.
Your goal is to write a Python FUNCTION that applies these headers and footers to the translated.pdf in English, adding a specific visual style.

Input Data:
{json_data_string}

Critical Technical Requirements:
1. Coordinate System (Permille): The x/y values are 0-1000 relative to page size. 
   Formula: actual = (permille_val / 1000.0) * page_dimension.
2. Visual Element: Draw a horizontal separator line slightly below the header text on every page.
3. Dependencies: Use `fitz` (PyMuPDF).

Step-by-Step Logic for the Function:
1. Define a function named exactly `process_pdf(input_path, output_path)`.
2. Inside the function:
   - Import `fitz` inside the function or at the top.
   - Embed the logic to handle the layout patterns derived from the Input Data.
   - Iterate through pages of `input_path`.
   - Calculate coordinates dynamically based on `page.rect`.
   - Insert translated English text (Header/Footer).
   - Draw the separator line.
   - Save the result to `output_path`.

Style Rules:
- Text: Helvetica, size 9, color (0.3, 0.3, 0.3).
- Line: Width 0.5, color (0, 0, 0).

Output Constraint:
- Return ONLY the Python code.
- DO NOT include `if __name__ == "__main__":` or any example usage.
- The entry point must be the function `process_pdf`.
    """

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt_content
                }
            ],
            max_tokens=8000, # 保持足够的长度
            temperature=0.1  # 重要：写代码时保持低温度，确保逻辑严谨，不要用 1
        )
        
        content = response.choices[0].message.content
        return content

    except Exception as e:
        print(f"❌ API 请求失败: {e}")
        return None

def clean_code(llm_response):
    """清洗 LLM 返回的 Markdown 标记"""
    if not llm_response:
        return ""
    pattern = r"```(?:python)?\n(.*?)```"
    match = re.search(pattern, llm_response, re.DOTALL)
    if match:
        return match.group(1)
    return llm_response

def execute_generated_code(code_string, input_path, output_path):
    """动态编译并执行代码"""
    print("⚡ 正在编译并执行生成的代码...")
    
    # 1. 准备执行上下文
    local_scope = {}
    # 传入当前的全局变量，确保 fitz 等库可用，虽然 LLM 代码里通常也会 import
    global_scope = globals().copy() 

    try:
        # 2. 编译并执行定义（此时 process_pdf 函数被加载到 local_scope）
        exec(code_string, global_scope, local_scope)
        
        # 3. 查找目标函数
        target_func = local_scope.get('process_pdf')
        
        # 备选查找逻辑
        if not callable(target_func):
            for name, obj in local_scope.items():
                if callable(obj) and name != 'fitz' and name != 'OpenAI': 
                    target_func = obj
                    break
        
        if not callable(target_func):
            raise ValueError("LLM 生成的代码中没有找到可执行的函数定义。")

        # 4. 调用函数
        print(f"📄 处理文件: {input_path}")
        target_func(input_path, output_path)
        
        if os.path.exists(output_path):
            print(f"✅ 成功! 输出文件已生成: {output_path}")
        else:
            print("⚠️ 函数执行完毕，但未检测到输出文件。")

    except Exception as e:
        print(f"❌ 代码执行出错:\n{e}")
        print("-" * 30)
        print("出错的代码如下：")
        print(code_string)
        print("-" * 30)


def _generate_code_for_json(json_path):
    """在后台线程中调用大模型生成代码，返回清洗后的代码字符串。"""
    json_data = load_header_candidates(json_path)
    if not json_data:
        raise ValueError("无法读取或解析 JSON 数据。")

    raw_code = generate_code_from_llm(json_data)
    if not raw_code:
        raise RuntimeError("大模型未返回代码。")

    return clean_code(raw_code)


def request_llm_in_background(json_path):
    """
    异步请求 LLM 生成代码，返回 Future。
    可在上游流程开始时调用，等 PDF 准备好后再取 result。
    """
    return _executor.submit(_generate_code_for_json, json_path)


def apply_header_when_ready(code_future, pdf_path, output_path=None, timeout=None):
    """
    等待代码生成完成后，对 PDF 应用页眉页脚。

    :param code_future: request_llm_in_background 返回的 Future
    :param pdf_path: 输入 PDF
    :param output_path: 可选，指定输出 PDF 路径；默认在原文件名后加 _with_header
    :param timeout: 可选，等待超时时间（秒）
    :return: 输出 PDF 路径
    """
    code_string = code_future.result(timeout=timeout)

    base, ext = os.path.splitext(pdf_path)
    output_pdf_path = output_path or f"{base}_with_header{ext}"

    execute_generated_code(code_string, pdf_path, output_pdf_path)

    if not os.path.exists(output_pdf_path):
        raise RuntimeError("处理完成但未检测到输出文件。")

    return output_pdf_path


def run_header_engine(json_path, pdf_path):
    """
    将主流程封装为可复用函数。

    :param json_path: header_candidates JSON 文件路径
    :param pdf_path: 已翻译 PDF 文件路径
    :return: 生成的带页眉页脚的 PDF 路径
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"找不到 JSON 文件: {json_path}")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"找不到输入 PDF 文件: {pdf_path}")

    base, ext = os.path.splitext(pdf_path)
    output_pdf_path = f"{base}_with_header{ext}"

    json_data = load_header_candidates(json_path)
    if not json_data:
        raise ValueError("无法读取或解析 JSON 数据。")

    raw_code = generate_code_from_llm(json_data)
    if not raw_code:
        raise RuntimeError("大模型未返回代码。")

    clean_script = clean_code(raw_code)
    execute_generated_code(clean_script, pdf_path, output_pdf_path)

    if not os.path.exists(output_pdf_path):
        raise RuntimeError("处理完成但未检测到输出文件。")

    return output_pdf_path


# --- 主程序入口 ---
if __name__ == "__main__":
    try:
        # 如果没有 PDF，生成一个假的用于测试
        if not os.path.exists(INPUT_PDF_PATH):
            print("提示: 输入 PDF 不存在，生成一个空白 PDF 用于测试...")
            doc = fitz.open()
            doc.new_page()
            doc.new_page()
            doc.save(INPUT_PDF_PATH)
            doc.close()

        result = run_header_engine(INPUT_JSON_PATH, INPUT_PDF_PATH)
        print(f"✅ 成功! 输出文件: {result}")
    except Exception as e:
        print(f"❌ 处理失败: {e}")