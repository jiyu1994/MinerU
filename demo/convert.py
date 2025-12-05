# convert.py
import subprocess
import os
import sys

def md_to_pdf_windows(md_file_path):
    # 1. 获取绝对路径，防止相对路径在 Node 中出错
    abs_md_path = os.path.abspath(md_file_path)
    
    if not os.path.exists(abs_md_path):
        print(f"❌ 错误: 文件不存在 -> {abs_md_path}")
        return

    # 2. 定位 bridge.js
    current_dir = os.path.dirname(os.path.abspath(__file__))
    bridge_script = os.path.join(current_dir, "bridge.js")

    print(f"🚀 开始转换: {abs_md_path}")

    try:
        # 3. 调用 Node
        # shell=True 在 Windows 有时能解决找不到命令的问题，但一般不需要
        # encoding='utf-8' 非常重要，否则 Windows 控制台可能报 gbk 错误
        process = subprocess.run(
            ["node", bridge_script, abs_md_path],
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8', 
            errors='replace' # 防止特殊字符导致 Python 崩溃
        )
        
        print(process.stdout)
        print(f"✅ 转换完成！PDF 应该在同目录下。")

    except subprocess.CalledProcessError as e:
        print("❌ 转换失败！Node.js 报错如下：")
        print(e.stderr)
    except FileNotFoundError:
        print("❌ 错误: 未找到 'node' 命令。请确保你安装了 Node.js 并且添加到了环境变量 Path 中。")

if __name__ == "__main__":
    # 在这里填入你的文件名，Windows 路径建议前面加 r 防止转义，或者用双反斜杠
    # 例如: r"D:\Documents\test.md"
    target_file = "test.md" 
    
    md_to_pdf_windows(target_file)