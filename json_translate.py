import json
import os
import shutil

from ai_translate import build_translate_embed, translate_json
from config import MODS_DIR, VERSION_JSON, EN_OUT_DIR, ZH_OUT_DIR, MERGED_EN_FILE, MERGED_ZH_FILE, MERGED_MAP_FILE, WORK_DIR, CFPA_PATH, CFPA_PROJECT_VERSION
from language_extract import extract_minecraft_langs, extract_mod_langs, merge_lang_json, generate_lang_map, extract_cfpa


def prepare():
    # 1. 提取模组包、官方资源包、CFPA的翻译 json，存储到 en 和 zh 目录
    extract_minecraft_langs(VERSION_JSON, EN_OUT_DIR, ZH_OUT_DIR)
    extract_mod_langs(MODS_DIR, EN_OUT_DIR, ZH_OUT_DIR)
    extract_cfpa(CFPA_PATH, CFPA_PROJECT_VERSION, EN_OUT_DIR, ZH_OUT_DIR)

    # 2. 合并语言文件
    merge_lang_json(ZH_OUT_DIR, MERGED_ZH_FILE)
    merge_lang_json(EN_OUT_DIR, MERGED_EN_FILE)

    # 3. 创建映射文件
    generate_lang_map(
        MERGED_EN_FILE,
        MERGED_ZH_FILE,
        MERGED_MAP_FILE,
        WORK_DIR + '/untranslated.json',
        WORK_DIR + '/exist_translated.json' # 追加额外已翻译的文本用于参考
    )

    # 4. 创建向量索引
    build_translate_embed(MERGED_MAP_FILE)

    # 5. 重新创建需要翻译的文件
    shutil.rmtree(EN_OUT_DIR)
    shutil.rmtree(ZH_OUT_DIR)
    extract_mod_langs(MODS_DIR, EN_OUT_DIR, ZH_OUT_DIR)
    merge_lang_json(ZH_OUT_DIR, MERGED_ZH_FILE)
    merge_lang_json(EN_OUT_DIR, MERGED_EN_FILE)
    generate_lang_map(
        MERGED_EN_FILE,
        MERGED_ZH_FILE,
        MERGED_MAP_FILE,
        WORK_DIR + '/untranslated.json'
    )

def split_translated(translated_file, en_dir, out_dir):
    # 存储每个键的命名空间
    namespace_map = {}

    # 遍历目录中的所有 JSON 文件
    for filename in os.listdir(en_dir):
        if filename.endswith('.json'):
            namespace = filename.split('.', 1)[0]
            file_path = os.path.join(en_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    # 合并对象
                    for key, value in data.items():
                        if key not in namespace_map:
                            namespace_map[key] = namespace
                except json.JSONDecodeError as e:
                    print(f"解析文件 {filename} 时出错: {e}")

    translated_map = {}
    # 读取已翻译文件
    with open(translated_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for key, value in data.items():
            known_namespace = namespace_map.get(key)
            if known_namespace is None:
                known_namespace = 'unknown'
            if known_namespace in translated_map:
                translated_map[known_namespace][key] = value
            else:
                translated_map[known_namespace] = {key: value}
    for namespace, translations in translated_map.items():
        out_file = os.path.join(out_dir, namespace, 'lang', 'zh_cn.json')
        out_basedir = os.path.dirname(out_file)
        os.makedirs(out_basedir, exist_ok=True)
        results = dict(sorted(translations.items()))
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)


def do_translate():
    translate_json(WORK_DIR + '/untranslated.json', WORK_DIR + '/translated.json')
    split_translated(WORK_DIR + '/translated.json', EN_OUT_DIR, WORK_DIR + '/translated')

if __name__ == '__main__':
    prepare()

    do_translate()