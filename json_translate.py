from ai_translate import build_translate_embed, translate_json
from config import MODS_DIR, EN_OUT_DIR, ZH_OUT_DIR, MERGED_EN_FILE, MERGED_ZH_FILE, MERGED_MAP_FILE, WORK_DIR
from language_extract import extract_mod_langs, merge_lang_json, generate_lang_map

def prepare():
    # 1. 提取模组包的翻译 json，存储到 en 和 zh 目录
    extract_mod_langs(MODS_DIR, EN_OUT_DIR, ZH_OUT_DIR)

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

def do_translate():
    translate_json(WORK_DIR + '/untranslated.json', WORK_DIR + '/translated.json')

if __name__ == '__main__':
    prepare()

    do_translate()