import re
import sys
import os

def advanced_fix_markdown(input_path):
    if not os.path.exists(input_path):
        print(f"❌ 错误: 找不到文件 '{input_path}'")
        return

    # 生成输出文件名 (原文件名_v2.md)
    file_dir, file_name = os.path.split(input_path)
    name, ext = os.path.splitext(file_name)
    output_path = os.path.join(file_dir, f"{name}_v2{ext}")

    print(f"🔧 正在执行深度修复: {input_path}")
    print("-" * 50)

    stats = {
        "figure_tags": 0, # 修复 <Figure ...>
        "latex_vec": 0,   # 修复 \Vec
        "latex_ref": 0,   # 修复 \ref
        "other_tags": 0   # 修复其他疑似标签
    }

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        fixed_lines = []

        # --- 正则表达式 ---
        
        # 1. 强力修复模式：专门针对 Figure 和 Table，无视是否包含数学公式
        # 匹配 <Figure ...> 或 <Table ...>，即使里面有 $ 符号
        # 解释: < ((Figure|Table) [非>]*) >
        strong_tag_pattern = re.compile(r'<((?:Figure|Table)[^>]*?)>')

        # 2. 通用修复模式：针对其他大写开头的伪标签 (如 <Image 1>)
        # 这个为了安全，依然只在没有 $ 的行运行
        general_tag_pattern = re.compile(r'<([A-Z][a-zA-Z0-9\s\.\-_]*?)>')

        # 3. LaTeX 修复
        vec_pattern = re.compile(r'\\Vec\b')
        ref_pattern = re.compile(r'\\ref\s*\{([^}]*)\}')

        for line in lines:
            new_line = line

            # --- 步骤 1: 强力修复 Figure/Table (解决 PDF 缩进的核心) ---
            # 只要发现 <Figure ...> 就把尖括号去掉，保留里面的内容
            matches = strong_tag_pattern.findall(new_line)
            if matches:
                new_line = strong_tag_pattern.sub(r'\1', new_line)
                stats["figure_tags"] += len(matches)

            # --- 步骤 2: 通用修复 (仅针对非公式行) ---
            # 如果行里没有 $，或者是代码块之外，检查是否有其他大写伪标签
            if '$' not in new_line and '`' not in new_line:
                matches_gen = general_tag_pattern.findall(new_line)
                if matches_gen:
                    new_line = general_tag_pattern.sub(r'\1', new_line)
                    stats["other_tags"] += len(matches_gen)

            # --- 步骤 3: LaTeX 语法修复 ---
            if vec_pattern.search(new_line):
                new_line = vec_pattern.sub(r'\\vec', new_line)
                stats["latex_vec"] += 1
            
            if ref_pattern.search(new_line):
                # 将 \ref{GE:24.2Q} 替换为 GE:24.2Q
                new_line = ref_pattern.sub(r'\1', new_line)
                stats["latex_ref"] += 1

            fixed_lines.append(new_line)

        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(fixed_lines)

        print(f"✅ 修复完成！\n💾 已保存为: {output_path}")
        print("-" * 50)
        print(f"📊 修复统计:")
        print(f"   - 强制剥离 <Figure/Table> 标签: {stats['figure_tags']} 处 (含数学公式行)")
        print(f"   - 修复其他伪标签: {stats['other_tags']} 处")
        print(f"   - 修正 \\Vec -> \\vec: {stats['latex_vec']} 处")
        print(f"   - 清理 \\ref 引用: {stats['latex_ref']} 处")
        print("-" * 50)

    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    # 如果你在命令行运行，可以传参数；否则默认使用你刚才的文件名
    filename = "2025_translated_fixed.md" # 默认输入文件名
    
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        
    advanced_fix_markdown(filename)