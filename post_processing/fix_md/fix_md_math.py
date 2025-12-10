import re
import sys
import os

def ocr_special_fix(formula: str) -> str:
    """
    用来修复一些典型的 OCR 误识别模式。
    例如： % 被识别成 \mathfrak { q } _ { 0 }
    """

    # 1. 把 \mathfrak { q } _ { 0 } 识别回 \%
    # 它中间有很多空格，全部宽松匹配
    formula = re.sub(
        r'\\mathfrak\s*\{\s*q\s*\}\s*_?\s*\{\s*0\s*\}',
        r'\\%',
        formula
    )

    # 也可以再加一个"无大括号版本"的兜底：
    formula = re.sub(
        r'\\mathfrak\s*q\s*_?\s*0',
        r'\\%',
        formula
    )

    # 2) 以及类似的 \mathfrak{c} 也可以粗暴映射成 %
    #    (如果你觉得太激进，也可以映射成空字符串或普通 c)
    formula = re.sub(
        r'\\mathfrak\s*\{\s*c\s*\}',
        r'\\%',
        formula
    )

    # 3) \sharp 基本就是 # 号
    formula = re.sub(
        r'\\sharp\b',
        r'\\#',
        formula
    )

    # 4) \frac{\mathfrak c}{\sharp} 这种“分母是 sharp 的怪分数”
    #    很大概率是被用来画一个奇怪符号，可以直接退化成 \%
    #    如果你不放心，也可以改成 '' 或 '\text{#}'
    formula = re.sub(
        r'\\frac\s*\{\s*\\mathfrak\s*\{\s*c\s*\}\s*\}\s*\{\s*\\#\s*\}',
        r'\\%',
        formula
    )

    # 5) 把 ^{\{ \% , } 这类怪 superscript 改成 ^{\%}
    #    允许中间各种空格
    formula = re.sub(
        r'\^\s*\\\{\s*\\%\s*,\s*\}',
        r'^{\\%}',
        formula
    )

    # 6) \mathrm { y o y } -> \mathrm{yoy}
    #    更通用: 去掉 \mathrm{...} 内部的所有空格
    def _join_inside_rm(m):
        inner = m.group(1)
        inner = re.sub(r'\\\s+', '', inner)   # "\ y" -> "y"
        inner = re.sub(r'\s+', '', inner)
        return r'\mathrm{' + inner + '}'

    formula = re.sub(
        r'\\mathrm\s*\{([^}]*)\}',
        _join_inside_rm,
        formula
    )

    return formula

def normalize_numbers(formula: str) -> str:
    """
    尽量把 OCR 打散的数字合并：
    - 0 . 9   -> 0.9
    - 1 , 0 8 6 -> 1,086
    - 2 . 0 0 { \sim } 2 . 2 5 -> 2.00 { \sim } 2.25
    - \ %  之类空格去掉
    """
    # "0 . 9" -> "0.9"
    formula = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', formula)

    # "1 , 0 8 6" -> 先合并逗号两边的空格
    formula = re.sub(r'(\d)\s*,\s*(\d)', r'\1,\2', formula)

    # 连续数字之间的空格直接去掉: "2 0 2 5" -> "2025"
    formula = re.sub(r'(\d)\s+(\d)', r'\1\2', formula)

    # "\ %" -> "\%"
    formula = re.sub(r'\\\s*%', r'\\%', formula)

    return formula

def balance_brackets(formula: str) -> str:
    open_to_close = {'(': ')', '[': ']', '{': '}'}
    close_to_open = {')': '(', ']': '[', '}': '{'}

    stack = []
    result = []
    prev = ''  # 记录前一个字符，用来识别 \{ / \}

    for ch in formula:
        if ch in open_to_close:
            if ch == '{' and prev == '\\':
                # 这是 \{，当普通字符处理，不参与栈
                result.append(ch)
            else:
                stack.append(ch)
                result.append(ch)
        elif ch in close_to_open:
            if ch == '}' and prev == '\\':
                # 这是 \}，当普通字符处理
                result.append(ch)
            else:
                if stack and stack[-1] == close_to_open[ch]:
                    stack.pop()
                    result.append(ch)
                else:
                    # 多出来的右括号丢掉
                    continue
        else:
            result.append(ch)
        prev = ch

    while stack:
        left = stack.pop()
        result.append(open_to_close[left])

    return ''.join(result)



def fix_formula_text(formula: str, stats: dict) -> str:
    """
    针对单个 $...$ 内的内容做修复：
    1. 数字规范化
    2. 括号平衡修补

    不再删除 $，也不再把“简单数值公式”退化成纯文本。
    """
    stats["math_segments"] = stats.get("math_segments", 0) + 1

    # 第 0 步：先修 OCR 特殊模式
    before_ocr = formula
    formula = ocr_special_fix(formula)
    if formula != before_ocr:
        stats["ocr_special_fixed"] = stats.get("ocr_special_fixed", 0) + 1

    # before = formula

    # 只在长度不太夸张且含数字的情况下做数字清洗，避免对很奇怪的长公式乱动
    if len(formula) <= 80 and re.search(r'\d', formula):
        formula = normalize_numbers(formula)

    before = formula
    fixed = balance_brackets(formula)
    if fixed != before:
        stats["math_bracket_fixed"] = stats.get("math_bracket_fixed", 0) + 1

    return fixed


def fix_math_in_line(line: str, stats: dict) -> str:
    """
    在一行中查找 $...$ / $$...$$，对内部公式调用 fix_formula_text。
    - 对 $$...$$ 保持 $$ 包裹
    - 对 $...$ 保持 $ 包裹
    """
    result = []
    i = 0
    n = len(line)

    while i < n:
        ch = line[i]
        if ch == '$':
            # 判断 display math: $$...$$
            if i + 1 < n and line[i+1] == '$':
                end = line.find('$$', i+2)
                if end != -1:
                    inner = line[i+2:end]
                    fixed_inner = fix_formula_text(inner, stats)
                    result.append('$$' + fixed_inner + '$$')
                    i = end + 2
                    continue
                else:
                    # 找不到闭合 $$，当普通字符处理
                    result.append(ch)
                    i += 1
                    continue
            else:
                # inline math: $...$
                end = line.find('$', i+1)
                if end != -1:
                    inner = line[i+1:end]
                    fixed_inner = fix_formula_text(inner, stats)
                    result.append('$' + fixed_inner + '$')
                    i = end + 1
                    continue
                else:
                    # 找不到闭合 $，当普通字符处理
                    result.append(ch)
                    i += 1
                    continue
        else:
            result.append(ch)
            i += 1

    return ''.join(result)



def advanced_fix_markdown(input_path):
    if not os.path.exists(input_path):
        print(f"❌ 错误: 找不到文件 '{input_path}'")
        return

    # 生成输出文件名 (原文件名_fixed.md)
    file_dir, file_name = os.path.split(input_path)
    name, ext = os.path.splitext(file_name)
    output_path = os.path.join(file_dir, f"{name}_fixed{ext}")

    print(f"🔧 正在执行深度修复: {input_path}")
    print("-" * 50)

    stats = {
        "figure_tags": 0,        # 修复 <Figure ...> / <Table ...>
        "latex_vec": 0,          # 修复 \Vec
        "latex_ref": 0,          # 修复 \ref
        "other_tags": 0,         # 修复其他伪标签
        "math_segments": 0,      # 处理的公式片段数
        "ocr_special_fixed": 0,
        "math_bracket_fixed": 0  # 做过括号修补的公式数量
    }

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        fixed_lines = []

        # --- 正则表达式 (沿用你原来的逻辑) ---

        # 1. 强力修复模式：专门针对 Figure 和 Table，无视是否包含数学公式
        # strong_tag_pattern = re.compile(r'<((?:Figure|Table)[^>]*?)>')
        strong_tag_pattern = re.compile(r'^\s*<\s*((?:Figure|Table)[^>\n]*?)>?')

        # 2. 通用修复模式：针对其他大写开头的伪标签 (如 <Image 1>)
        general_tag_pattern = re.compile(r'<([A-Z][a-zA-Z0-9\s\.\-_]*?)>')

        # 3. LaTeX 修复
        vec_pattern = re.compile(r'\\Vec\b')
        ref_pattern = re.compile(r'\\ref\s*\{([^}]*)\}')

        in_code_block = False  # 追踪 ``` 代码块，避免误改代码

        for line in lines:
            new_line = line

            stripped = new_line.strip()
            if stripped.startswith("```"):
                # 进入或退出代码块
                in_code_block = not in_code_block
                fixed_lines.append(new_line)
                continue

            # --- 步骤 1: 强力修复 Figure/Table (解决 PDF 缩进的核心) ---
            matches = strong_tag_pattern.findall(new_line)
            if matches:
                new_line = strong_tag_pattern.sub(r'\1', new_line)
                stats["figure_tags"] += len(matches)

            # --- 步骤 2: 通用伪标签修复 (仅针对非公式行、非代码行) ---
            if (not in_code_block) and ('$' not in new_line) and ('`' not in new_line):
                matches_gen = general_tag_pattern.findall(new_line)
                if matches_gen:
                    new_line = general_tag_pattern.sub(r'\1', new_line)
                    stats["other_tags"] += len(matches_gen)

            # --- 步骤 3: LaTeX 语法修复 (Vec/ref 等) ---
            if vec_pattern.search(new_line):
                new_line = vec_pattern.sub(r'\\vec', new_line)
                stats["latex_vec"] += 1

            if ref_pattern.search(new_line):
                # 将 \ref{GE:24.2Q} 替换为 GE:24.2Q
                new_line = ref_pattern.sub(r'\1', new_line)
                stats["latex_ref"] += 1

            # --- 步骤 4: 公式修复 ($...$ / $$...$$) ---
            if (not in_code_block) and ('$' in new_line):
                new_line = fix_math_in_line(new_line, stats)

            fixed_lines.append(new_line)

        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(fixed_lines)

        print(f"✅ 修复完成！\n💾 已保存为: {output_path}")
        print("-" * 50)
        print("📊 修复统计:")
        print(f"   - 强制剥离 <Figure/Table> 标签: {stats['figure_tags']} 处 (含数学公式行)")
        print(f"   - 修复其他伪标签: {stats['other_tags']} 处")
        print(f"   - 修正 \\Vec -> \\vec: {stats['latex_vec']} 处")
        print(f"   - 清理 \\ref{{...}} 引用 -> 文本: {stats['latex_ref']} 处")
        print(f"   - 处理公式片段 (含 $...$ / $$...$$): {stats['math_segments']} 处")
        # print(f"   - 识别为简单数值公式并去掉 $ 包裹: {stats['math_simple_numeric']} 处")
        print(f"   - 做过括号平衡修补的公式: {stats['math_bracket_fixed']} 处")
        print(f"   - OCR 特殊模式修复: {stats['ocr_special_fixed']} 处")
        print("-" * 50)

    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == "__main__":
    # 默认文件名可以自己改，这里给一个示例
    filename = "2025_translated.md"

    if len(sys.argv) > 1:
        filename = sys.argv[1]
    
    advanced_fix_markdown(filename)
        