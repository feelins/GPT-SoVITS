#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def extract_phonemes(input_file, output_file):
    """
    从发音词典中提取所有独特的音素，并保存到文件。

    Args:
        input_file (str): 输入词典文件路径
        output_file (str): 输出音素列表文件路径
    """
    phonemes = set()
    index = 0
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            index += 1
            if index < 56:
                continue
            
            line = line.strip()
            if not line:                # 跳过空行
                continue
            parts = line.split()  # 使用两个空格分隔词条和音素
            if len(parts) < 2:          # 至少需要一个词条和一个音素
                continue
            # 第一个字段是词条，其余都是音素
            phonemes.update(parts[1:])

    # 按字母顺序排序（音素符号通常包含数字，排序仍按字符串处理）
    sorted_phonemes = sorted(phonemes)

    with open(output_file, 'w', encoding='utf-8') as f:
        for p in sorted_phonemes:
            f.write(p + '\n')

    print(f"共找到 {len(sorted_phonemes)} 个独特音素，已保存到 {output_file}")


if __name__ == "__main__":
    input_dict_file = r'/Users/feelins/works/GPT-SoVITS/GPT_SoVITS/text/cmudict.rep'
    output_list_file = r'/Users/feelins/works/GPT-SoVITS/GPT_SoVITS/text/cmudict_phon.list'
    extract_phonemes(input_dict_file, output_list_file)