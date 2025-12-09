import json
import os
import math


import re
from collections import defaultdict

def extract_footers(data_list, y_tolerance=10, x_tolerance=20):
    """
    从OCR数据中分离页脚和正文/引用。
    
    Args:
        data_list: 包含 {'text', 'x', 'y', ...} 的字典列表
        y_tolerance: Y轴坐标容差（像素），用于忽略OCR抖动
        x_tolerance: X轴坐标容差（像素）
        
    Returns:
        footers: 被识别为页脚的数据列表
        others: 其他数据（引用、正文等）
    """
    
    # 1. 定义一个辅助函数来生成“骨架”
    def get_skeleton(text):
        # 将所有连续数字替换为 {N}
        # 如果需要更通用的，也可以将非ASCII字符替换，但通常数字替换就足够处理页码了
        return re.sub(r'\d+', '{N}', text)

    # 2. 定义坐标分桶（Binning）
    def get_location_key(x, y):
        # 将坐标除以容差并取整，强制让相近的坐标归为同一类
        bin_y = round(y / y_tolerance) * y_tolerance
        bin_x = round(x / x_tolerance) * x_tolerance
        return (bin_x, bin_y)

    # 3. 聚类分析
    # key = (骨架字符串, 近似X, 近似Y)
    # value = 属于这个模式的所有原始数据项
    clusters = defaultdict(list)
    
    for item in data_list:
        text = item.get('text', '')
        x = float(item.get('x', 0))
        y = float(item.get('y', 0))
        
        skeleton = get_skeleton(text)
        loc_key = get_location_key(x, y)
        
        # 组合特征：骨架 + 位置
        # 只有“内容模式”和“位置”都匹配，才被视为同一类元素
        cluster_key = (skeleton, loc_key)
        clusters[cluster_key].append(item)

    

    return clusters

def create_final_markdown(others_list, source_md_path):
    """
    读取源MD，拼接带有明显分割线的 Endnotes，保存为新文件 (_final.md)

    Returns:
        str: 新生成的文件路径，如果失败则返回 None
    """
    if not os.path.exists(source_md_path):
        print(f"❌ 错误：源文件 {source_md_path} 不存在。")
        return None

    # 1. 确定输出文件名
    base, ext = os.path.splitext(source_md_path)
    output_md_path = f"{base}_final{ext}"

    # 2. 读取原始正文
    with open(source_md_path, 'r', encoding='utf-8') as f:
        original_content = f.read()

    # 3. 构建 Endnotes 内容
    endnotes_content = ""

    if others_list:
        endnotes_content += "\n\n"

        # --- 视觉分隔区域 Start ---

        # 1. 先空几行 (使用 <br> 标签确保垂直间距不被 Markdown 吞掉)
        endnotes_content += "<br><br><br>\n\n"

        # 2. 明显的分割线 (使用 HTML <hr> 可以控制粗细和颜色)
        #    border-top: 2px solid #000;  表示 2像素宽的黑色实线
        #    margin: 30px 0; 表示上下再留点间距
        endnotes_content += '<hr style="border: 0; border-top: 2px solid #333; margin: 30px 0;">\n\n'

        # 3. 分割线后再空一行，不让标题贴太紧
        endnotes_content += "<br>\n\n"

        # (可选) 如果你依然希望 Endnotes 独占一页，请取消下面这行的注释：
        # endnotes_content += '<div style="page-break-before: always;"></div>\n\n'

        # --- 视觉分隔区域 End ---

        # 标题
        endnotes_content += "### Endnotes\n\n"

        for item in others_list:
            # 清理换行
            clean_item = item.replace('\n', ' ').strip()

            # 转义数字编号 (1. -> 1\.)，保留原始编号，防止变列表
            clean_item = re.sub(r'^(\d+)([\.\)])', r'\1\\\2', clean_item)

            # 写入段落
            endnotes_content += f"{clean_item}\n\n"
    else:
        print(">>> 没有发现 Others 内容，仅复制原文件。")

    # 4. 写入新文件
    try:
        final_content = original_content + endnotes_content
        with open(output_md_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        print(f">>> ✅ 成功生成最终文件: {output_md_path}")
        if others_list:
            print(f"    (已追加 {len(others_list)} 条 Endnotes，含分割线)")
        return output_md_path
    except Exception as e:
        print(f"❌ 写入文件失败: {e}")
        return None


def analyze_layout(SOURCE_JSON, OUTPUT_CONFIG, MarkDownPath):
    if not os.path.exists(SOURCE_JSON):
        print(f"❌ 错误：找不到文件 {SOURCE_JSON}")
        return

    print(f">>> 正在分析布局数据: {SOURCE_JSON}...")
    
    with open(SOURCE_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. 初始化变量
    # 我们需要找到所有元素中，最极端的坐标，从而推断页面大小和正文边界
    max_page_x = 0
    max_page_y = 0
    
    min_body_top = float('inf')    # 正文起始 Y
    max_body_bottom = float('-inf') # 正文结束 Y
    min_body_left = float('inf')   # 正文起始 X
    max_body_right = float('-inf') # 正文结束 X

    header_candidates = []
    footer_candidates = []

    # 2. 遍历数据，收集坐标
    for item in data:
        bbox = item.get('bbox')
        if not bbox or len(bbox) != 4:
            continue
        
        # MinerU bbox 格式: [x0, y0, x1, y1]
        x0, y0, x1, y1 = bbox
        


        if item.get('type') == 'discarded':
            # 暂时收集所有被丢弃的文本，稍后根据最终页面高度判断位置
            # 存入中心点 x 坐标，方便判断左右
            center_x = (x0 + x1) / 2
            item_data = {'text': item.get('text', ''), 'x': x0, 'y': y1, 'center_x': center_x}
            
            # 这里先不区分 header/footer，等确定页面高度后再分
            header_candidates.append(item_data) 
        else:
            # 正文内容：用来严格界定页边距
            min_body_top = min(min_body_top, y0)
            max_body_bottom = max(max_body_bottom, y1)
            min_body_left = min(min_body_left, x0)
            max_body_right = max(max_body_right, x1)

    # 3. 使用 MinerU 的千分比坐标系 (1000 x 1000)

    # 4. 区分页眉和页脚
    # 阈值：页面顶部 15% 为页眉区，底部 15% 为页脚区 (千分比)
    header_threshold = 150  # 1000 * 0.15
    footer_threshold = 850  # 1000 * 0.85
    
    real_headers = []
    real_footers = []
    # 这里复用之前的 candidates，它们的坐标已经是千分比
    for item in header_candidates:
        if item['y'] < header_threshold:
            real_headers.append(item)
        elif item['y'] > footer_threshold:
            real_footers.append(item)

    # 5. 提取页眉文字 (左/右)
    # 按 x 坐标排序
    real_headers.sort(key=lambda k: k['x'])

    header_left = ""
    header_right = ""
    header_y = 0  # 初始化默认值

    if real_headers:
        # 最左边的
        header_left = real_headers[0]['text']
        header_y = real_headers[0]['y']
        # 找最右边的 (必须在页面右半部分)
        last = real_headers[-1]
        # 判断是否在页面右侧 (x > 宽度的一半)
        if last['x'] > 500:  # 1000 / 2
            # 且不能和左边的一样
            if last['text'] != header_left:
                header_right = last['text']

    # 6. 提取页脚文字
    clusters = extract_footers(real_footers)
    others = []
    real_footers = []
    for cluster_items in clusters.values():
        if len(cluster_items) == 1:
            others.append(cluster_items[0]['text'])
        else:
            for item in cluster_items:
                real_footers.append(item)
    


    real_footers.sort(key=lambda k: k['x'])

    footer_left = ""
    footer_right = ""
    footer_y = 0  # 初始化默认值
    if real_footers:
        footer_left = real_footers[0]['text']
        footer_y = real_footers[0]['y']
        last = real_footers[-1]
        if last['x'] > 500:  # 1000 / 2
            if last['text'] != footer_left:
                footer_right = last['text']

    # 7. 计算精确边距 (千分比)
    # MinerU 的千分比坐标系中，边距就是坐标值本身
    margin_top = min_body_top
    margin_bottom = 1000 - max_body_bottom
    margin_left = min_body_left
    margin_right = 1000 - max_body_right

    # 安全钳位 (防止负数或过小，千分比单位)
    margin_top = max(10, margin_top)
    margin_bottom = max(10, margin_bottom)
    margin_left = max(10, margin_left)
    margin_right = max(10, margin_right)

    # 坐标已经是千分比单位，无需转换

    # 8. 生成结果 (千分比单位)
    result = {
        "page_size": {
            "width": "1000",
            "height": "1000",
            "unit": "permille"
        },
        "margins": {
            "top": f"{margin_top:.0f}",
            "bottom": f"{margin_bottom:.0f}",
            "left": f"{margin_left:.0f}",
            "right": f"{margin_right:.0f}",
            "unit": "permille"
        },
        "header": {
            "left": header_left,
            "right": header_right,
            "y": f"{header_y:.0f}",
            "unit": "permille"
        },
        "footer": {
            "left": footer_left,
            "right": footer_right,
            "y": f"{footer_y:.0f}",
            "unit": "permille"
        },
        "others": others
    }

    # 9. 写入文件
    with open(OUTPUT_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    
    print(f">>> ✅ 成功生成配置: {OUTPUT_CONFIG}")
    print(json.dumps(result, indent=4, ensure_ascii=False))

    return create_final_markdown(others, MarkDownPath)

if __name__ == "__main__":
    # ================= 配置区 =================
    SOURCE_JSON = "demo/output/2025/auto/2025_content_list.json"  # MinerU 生成的 json 路径
    OUTPUT_CONFIG = "demo/output/2025/auto/2025_layout_config.json"         # 输出给 Node.js 用的配置
    MarkDownPath = "demo/output/2025/auto/2025_translated_v2.md"
# =========================================
    analyze_layout(SOURCE_JSON, OUTPUT_CONFIG, MarkDownPath)
