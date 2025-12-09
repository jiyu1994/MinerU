from __future__ import annotations

import argparse
from typing import Iterable, List, Tuple

TitleEntry = Tuple[int, str]


def load_titles(markdown_path: str) -> List[TitleEntry]:
    """收集原始 markdown 中的标题行，保留行号和原文内容."""
    titles: List[TitleEntry] = []
    with open(markdown_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.startswith("# "):
                titles.append((idx, line.rstrip("\n")))
    return titles


def build_prompt(titles: Iterable[TitleEntry]) -> str:
    """根据标题列表构造给大模型的提示词."""
    prompt_lines = [
        "下面是一篇文章的所有段落标题，前面是行号，后面是内容。",
        "请判断每个标题属于第几级：一级以一个 # 开头，二级以两个 # 开头，以此类推。",
        "请返回修改后的列表，形如 [[行号, 修正后的标题文本], ...]，只调整 # 的数量并可修正标题措辞。",
        "",
        "标题列表：",
    ]
    for idx, title in titles:
        prompt_lines.append(f"{idx}: {title}")
    return "\n".join(prompt_lines)


def call_model_for_titles(titles: List[TitleEntry]) -> List[TitleEntry]:
    """
    调用大模型修正标题级别并返回更新后的列表。

    TODO: 使用实际的大模型接口实现此函数。建议使用 build_prompt(titles)
    生成提示词，并将返回结果解析为 [行号, 修正标题] 的列表。
    """
    prompt = build_prompt(titles)
    # 在此处调用大模型 API，并将 prompt 传入。
    # 返回值需是 [(line_index, fixed_title), ...]，fixed_title 中包含正确数量的 #。
    raise NotImplementedError("请实现大模型调用逻辑")


def apply_titles_to_markdown(
    markdown_path: str, updated_titles: List[TitleEntry], output_path: str | None = None
) -> None:
    """将大模型返回的标题写回到 markdown 文件."""
    with open(markdown_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    replacements = {idx: title for idx, title in updated_titles}
    for idx, new_title in replacements.items():
        # 确保末尾换行
        lines[idx] = new_title.rstrip("\n") + "\n"

    target = output_path or markdown_path
    with open(target, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main(markdown_path: str, output_path: str | None = None) -> None:
    titles = load_titles(markdown_path)
    updated_titles = call_model_for_titles(titles)
    apply_titles_to_markdown(markdown_path, updated_titles, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="使用大模型修正 Markdown 标题级别")
    parser.add_argument("markdown_path", help="待处理的 markdown 文件路径")
    parser.add_argument("-o", "--output", dest="output_path", help="输出文件路径，默认覆盖输入文件")
    args = parser.parse_args()
    main(args.markdown_path, args.output_path)
