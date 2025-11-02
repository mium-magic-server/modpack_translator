import os

import ftb_snbt_lib as slib

from ai_translate import translate_dict
from config import WORK_DIR


def dict_to_slib(data: dict) -> slib.Compound:
    result = slib.Compound()
    for key, value in data.items():
        if isinstance(value, list):
            slib_list = []
            for item in value:
                slib_list.append(slib.String(item))
            result[key] = slib.List(slib_list)
        elif isinstance(value, str):
            result[key] = slib.String(value)
    return result

def translate_snbt_lang(input_snbt, output_snbt):
    with open(input_snbt, 'r', encoding='utf-8') as f:
        tag = slib.load(f)
    output = translate_dict(tag)
    with open(output_snbt, 'w', encoding='utf-8') as f:
        slib.dump(dict_to_slib(output), f)

def translate_quests(dir_path='quests/lang/en_us', out_path='quests/lang/zh_cn'):
    # translate_snbt_lang(vectorstore, 'ftbquests/lang/en_us.snbt', 'ftbquests/lang/zh_cn.snbt')
    for root, paths, files in os.walk(dir_path):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, dir_path).replace(os.sep, '/')
            if rel_path.endswith('.snbt'):
                out_full_path = os.path.join(out_path, rel_path)
                if os.path.exists(out_full_path):
                    continue
                out_dirname = os.path.dirname(out_full_path)
                if not os.path.exists(out_dirname):
                    os.makedirs(out_dirname)
                translate_snbt_lang(full_path, out_full_path)


if __name__ == '__main__':
    translate_quests(WORK_DIR + '/ftbquests/quests/lang/en_us', WORK_DIR + '/ftbquests/quests/lang/zh_cn')
