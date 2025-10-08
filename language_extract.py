import json
import os
import sys
import zipfile
import fnmatch

# 读取 JSON 文件
def read_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 写入 JSON 文件
def write_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_lang_to_json(lang_content):
    """
    将 key=value 格式的字符串转换为 Dict 对象
    """
    result = {}
    for line in lang_content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):  # 忽略注释
            if '=' in line:
                key, value = line.split('=', 1)
                result[key.strip()] = value.strip()
    return result

def extract_mod_langs(mods_dir, en_output_dir, zh_output_dir, need_parse = False):
    """
    提取 mods 目录所有 jar 文件的 assets/*lang/*.json 语言文件
    :param mods_dir: mods 目录
    :param en_output_dir: 英语 json 输出目录
    :param zh_output_dir: 目标语言 json 输出目录
    :param need_parse: 是否要处理 .lang 文件
    :return: None
    """
    # 创建输出目录
    os.makedirs(en_output_dir, exist_ok=True)
    os.makedirs(zh_output_dir, exist_ok=True)

    # 遍历 JAR 文件
    for zip_file in os.listdir(mods_dir):
        zip_path = os.path.join(mods_dir, zip_file)
        if not zip_path.endswith(".jar") and not zip_path.endswith(".zip"):
            continue

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 获取 ZIP 中所有文件名
                file_list = zip_ref.namelist()

                # 匹配 en_us.json 和 zh_cn.json 文件
                suffix = ".lang" if need_parse else ".json"
                en_files = [f for f in file_list if fnmatch.fnmatch(f, f"assets/*lang/en_us{suffix}")]
                zh_files = [f for f in file_list if fnmatch.fnmatch(f, f"assets/*lang/zh_cn{suffix}")]

                # 提取 en_us.lang 文件并转换为 JSON
                for en_file in en_files:
                    dir_name = os.path.basename(os.path.dirname(os.path.dirname(en_file)))
                    output_path = os.path.join(en_output_dir, f"{dir_name}.json")
                    try:
                        with zip_ref.open(en_file) as src:
                            content = src.read().decode()  # 假设是 UTF-8 编码
                            if need_parse:
                                json_data = parse_lang_to_json(content)
                            else:
                                json_data = json.loads(content)
                            write_json(json_data, output_path)
                        print(f"提取 en: {en_file} -> {output_path}")
                    except Exception as e:
                        print(f"读取 en 文件时出错: {en_file}, 错误: {e}")

                # 提取 zh_cn.lang 文件并转换为 JSON
                for zh_file in zh_files:
                    dir_name = os.path.basename(os.path.dirname(os.path.dirname(zh_file)))
                    output_path = os.path.join(zh_output_dir, f"{dir_name}.json")
                    try:
                        with zip_ref.open(zh_file) as src:
                            content = src.read().decode()
                            if need_parse:
                                json_data = parse_lang_to_json(content)
                            else:
                                json_data = json.loads(content)
                            write_json(json_data, output_path)
                        print(f"提取 zh: {zh_file} -> {output_path}")
                    except Exception as e:
                        print(f"读取 zh 文件时出错: {zh_file}, 错误: {e}")

        except zipfile.BadZipFile:
            print(f"跳过损坏的 ZIP 文件: {zip_path}")
        except Exception as e:
            print(f"处理 ZIP 文件时出错: {zip_path}, 错误: {e}")

def merge_lang_json(directory, output_file):
    # 存储最终合并后的对象
    merged_json = {}

    # 存储冲突的键
    conflict_keys = set()

    # 遍历目录中的所有 JSON 文件
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    # 合并对象
                    for key, value in data.items():
                        if key in merged_json:
                            conflict_keys.add(key)
                            print(f"[警告] 键 '{key}' 在文件 '{filename}' 中重复，将使用最后一次出现的值。")
                        merged_json[key] = value
                except json.JSONDecodeError as e:
                    print(f"解析文件 {filename} 时出错: {e}")

    # 打印所有冲突的键
    if conflict_keys:
        print(f"\n检测到以下键有冲突：{', '.join(conflict_keys)}")

    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    # 输出到文件
    write_json(merged_json, output_file)
    print(f"\n✅ 合并完成，结果保存在：{output_file}")

def generate_lang_map(merged_en_file, merged_zh_file, en2zh_file, untranslated_file, exist_translated_file):
    # 读取英文和中文翻译文件
    en_data = read_json(merged_en_file)
    zh_data = read_json(merged_zh_file)
    if exist_translated_file and os.path.exists(exist_translated_file):
        zh_data.update(read_json(exist_translated_file))

    # 存储翻译映射和未翻译的键
    en2zh = {}
    untranslated = {}

    # 遍历英文翻译
    for key in en_data:
        en_value = en_data[key]
        zh_value = zh_data.get(key)

        # 只处理字符串类型的值
        if isinstance(en_value, str):
            if isinstance(zh_value, str) and en_value != zh_value:
                en2zh[en_value] = zh_value
            else:
                untranslated[key] = en_value

    # 写入翻译映射和未翻译的键
    write_json(en2zh, en2zh_file)
    write_json(untranslated, untranslated_file)

    print(f"✅ 翻译映射已保存至: {en2zh_file}")
    print(f"⚠️ 未翻译的键已保存至: {untranslated_file}")