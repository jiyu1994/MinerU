import requests
import json
import os
import time

# ================= 配置区域 =================
# 1. 你的 API Key
API_KEY = "apikey-dd675b2a3fcb4f1aa88b91503d87f730" # 记得替换这里！

# 2. 文件路径
input_md_path = r"..\..\demo\output\2025\auto\2025.md"
output_md_path = r"..\..\demo\output\2025\auto\2025_translated.md"

# 3. API 设置
url = "https://api.atlascloud.ai/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}
# 是否在控制台实时打印流式返回内容；关闭后仍会写入文件
PRINT_STREAM_CONTENT = False
# ===========================================

def main():
    # 1. 读取 Markdown 文件
    if not os.path.exists(input_md_path):
        print(f"❌ 找不到文件: {input_md_path}")
        return

    print(f"📖 正在读取: {input_md_path}")
    with open(input_md_path, 'r', encoding='utf-8') as f:
        file_content = f.read()

    # 2. 准备提示词 (Prompt)
    system_prompt = """
    You are a professional academic paper translation expert. Your task is to translate academic papers in other languages formatted in Markdown into fluent English.

    【Strictly follow these rules】
    1. **Preserve formatting**: Never modify Markdown structures such as titles(#), lists(-), quotes(>).
    2. **Preserve images and links**: Content in formats like ![](...) or [](...) must be kept exactly as is, do not translate or modify the paths.
    3. **Preserve formulas**: LaTeX formulas ($$...$$ or $...$) must be kept exactly as is.
    4. **Preserve HTML tables**: If you encounter <table> tags, only translate the text in the cells without breaking the tag structure.
    5. **Professionalism**: Use professional academic terminology with formal tone.
    """

    # 3. 构造请求数据
    data = {
        "model": "openai/gpt-5.1",  # 确保你的供应商支持这个模型名
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please translate the following content into English, output only the translated Markdown directly without any additional content：\n\n{file_content}"}
        ],
        "max_tokens": 65536, # 这个数值足够大
        "temperature": 0.3,  # 翻译任务建议调低温度，更稳定
        "stream": True       # 开启流式传输，防止长文超时
    }

    print("🚀 开始发送请求并接收翻译流...")
    
    # 4. 发送请求并流式处理
    try:
        # stream=True 告诉 requests 这是一个流
        with requests.post(url, headers=headers, json=data, stream=True) as response:
            response.raise_for_status() # 检查是否有 HTTP 错误
            
            # 打开输出文件准备写入
            with open(output_md_path, 'w', encoding='utf-8') as f_out:
                bytes_written = 0
                report_step = 2000  # 每累计 2000 字符打印一次进度
                last_report = 0

                # 逐行读取网络流
                for line in response.iter_lines():
                    if line:
                        # 去掉开头的 "data: " 前缀
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith("data: "):
                            line_str = line_str[6:]
                        
                        # 结束标志
                        if line_str == "[DONE]":
                            break
                        
                        try:
                            # 解析 JSON 数据块
                            json_chunk = json.loads(line_str)

                            # 检查是否有错误信息
                            if 'error' in json_chunk:
                                print(f"API错误: {json_chunk['error']}")
                                continue

                            # 提取文本内容
                            if 'choices' in json_chunk and len(json_chunk['choices']) > 0:
                                try:
                                    content = json_chunk['choices'][0]['delta'].get('content', '')
                                except (IndexError, KeyError) as e:
                                    print(f"DEBUG: 提取content失败: {e}, 数据结构: {list(json_chunk.keys())}")
                                    continue
                            else:
                                print(f"DEBUG: choices为空或不存在，数据结构: {list(json_chunk.keys()) if isinstance(json_chunk, dict) else type(json_chunk)}")
                                continue

                            if content:
                                if PRINT_STREAM_CONTENT:
                                    print(content, end='', flush=True)
                                f_out.write(content)
                                bytes_written += len(content)
                                if bytes_written - last_report >= report_step:
                                    print(f"已接收约 {bytes_written} 字符")
                                    last_report = bytes_written

                        except json.JSONDecodeError:
                            print(f"DEBUG: 无法解析JSON: {line_str[:100]}...")
                            continue
                        except Exception as e:
                            print(f"DEBUG: 其他错误: {e}, 数据: {line_str[:100]}...")
                            continue

        print(f"\n\n✅ 翻译完成！文件已保存至: {output_md_path}")
        print("🎉 现在你可以用 Typora 或 VS Code 打开这个新文件查看效果了！")

    except Exception as e:
        print(f"\n❌ 请求出错: {e}")

def translate_file(input_path, output_path, api_key):
    """
    翻译单个文件的核心函数
    Args:
        input_path: 输入markdown文件路径
        output_path: 输出翻译文件路径
        api_key: API密钥
    Returns:
        bool: 翻译是否成功
    """
    # 1. 读取 Markdown 文件
    if not os.path.exists(input_path):
        print(f"❌ 找不到文件: {input_path}")
        return False

    print(f"📖 正在读取: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        file_content = f.read()

    # 2. 准备提示词 (Prompt)
    system_prompt = """
    You are a professional academic paper translation expert. Your task is to translate academic papers in other languages formatted in Markdown into fluent English.

    【Strictly follow these rules】
    1. **Preserve formatting**: Never modify Markdown structures such as titles(#), lists(-), quotes(>).
    2. **Preserve images and links**: Content in formats like ![](...) or [](...) must be kept exactly as is, do not translate or modify the paths.
    3. **Preserve formulas**: LaTeX formulas ($$...$$ or $...$) must be kept exactly as is.
    4. **Preserve HTML tables**: If you encounter <table> tags, only translate the text in the cells without breaking the tag structure.
    5. **Professionalism**: Use professional academic terminology with formal tone.
    """

    # 3. 构造请求数据
    data = {
        "model": "openai/gpt-5.1",  # 确保你的供应商支持这个模型名
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please translate the following content into English, output only the translated Markdown directly without any additional content：\n\n{file_content}"}
        ],
        "max_tokens": 65536, # 这个数值足够大
        "temperature": 0.3,  # 翻译任务建议调低温度，更稳定
        "stream": True       # 开启流式传输，防止长文超时
    }

    print("🚀 开始发送请求并接收翻译流...")

    # 4. 发送请求并流式处理，添加重试机制
    max_retries = 3
    idle_timeout = 180  # 单次尝试内的无数据超时时间（秒）
    for attempt in range(max_retries):
        try:
            print(f"第 {attempt + 1} 次尝试...")

            # 设置更长的超时时间
            with requests.post(url, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                             json=data, stream=True, timeout=600) as response:  # 10分钟超时
                response.raise_for_status()  # 检查是否有 HTTP 错误

                # 打开输出文件准备写入
                with open(output_path, 'w', encoding='utf-8') as f_out:
                    bytes_written = 0
                    report_step = 2000  # 每累计 2000 字符打印一次进度
                    last_report = 0
                    last_chunk_ts = time.time()

                    # 逐行读取网络流，添加超时和中断处理
                    try:
                        for line in response.iter_lines(chunk_size=1024):
                            now = time.time()
                            if line is None or line == b"":
                                if now - last_chunk_ts > idle_timeout:
                                    raise TimeoutError(f"流式传输{idle_timeout}s无数据，已中断")
                                continue

                            last_chunk_ts = now

                            # 去掉开头的 "data: " 前缀
                            line_str = line.decode('utf-8').strip()
                            if line_str.startswith("data: "):
                                line_str = line_str[6:]

                            # 结束标志
                            if line_str == "[DONE]":
                                break

                            try:
                                # 解析 JSON 数据块
                                json_chunk = json.loads(line_str)

                                # 检查是否有错误信息
                                if 'error' in json_chunk:
                                    print(f"API错误: {json_chunk['error']}")
                                    continue

                                # 提取文本内容
                                if 'choices' in json_chunk and len(json_chunk['choices']) > 0:
                                    try:
                                        content = json_chunk['choices'][0]['delta'].get('content', '')
                                    except (IndexError, KeyError) as e:
                                        print(f"DEBUG: 提取content失败: {e}, 数据结构: {list(json_chunk.keys())}")
                                        continue
                                else:
                                    print(f"DEBUG: choices为空或不存在，数据结构: {list(json_chunk.keys()) if isinstance(json_chunk, dict) else type(json_chunk)}")
                                    continue

                                if content:
                                    if PRINT_STREAM_CONTENT:
                                        print(content, end='', flush=True)
                                    f_out.write(content)
                                    bytes_written += len(content)
                                    if bytes_written - last_report >= report_step:
                                        print(f"已接收约 {bytes_written} 字符")
                                        last_report = bytes_written

                            except json.JSONDecodeError:
                                print(f"DEBUG: 无法解析JSON: {line_str[:100]}...")
                                continue
                            except Exception as e:
                                print(f"DEBUG: 其他错误: {e}, 数据: {line_str[:100]}...")
                                continue

                        print(f"\n\n✅ 翻译完成！文件已保存至: {output_path}")
                        print("🎉 现在你可以用 Typora 或 VS Code 打开这个新文件查看效果了！")
                        return True

                    except Exception as stream_error:
                        print(f"流式传输中断: {stream_error}")
                        if attempt < max_retries - 1:
                            print("准备重试...")
                            continue
                        else:
                            raise stream_error

        except requests.exceptions.Timeout:
            print(f"第 {attempt + 1} 次尝试超时")
            if attempt < max_retries - 1:
                print("准备重试...")
                continue
            else:
                print("❌ 所有重试都超时了")
                return False

        except requests.exceptions.ConnectionError as e:
            print(f"第 {attempt + 1} 次尝试连接错误: {e}")
            if attempt < max_retries - 1:
                print("准备重试...")
                continue
            else:
                print("❌ 所有重试都失败了")
                return False

        except Exception as e:
            print(f"第 {attempt + 1} 次尝试出错: {e}")
            if attempt < max_retries - 1:
                print("准备重试...")
                continue
            else:
                print("❌ 所有重试都失败了")
                return False

    return False


if __name__ == "__main__":
    # 测试函数版本
    import sys
    if len(sys.argv) > 3:
        input_path = sys.argv[1]
        output_path = sys.argv[2]
        api_key = sys.argv[3]
        translate_file(input_path, output_path, api_key)
    else:
        main()