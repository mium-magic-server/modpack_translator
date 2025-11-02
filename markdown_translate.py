import fnmatch
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from ai_translate import translate_document, load_translate_embed
from config import MODS_DIR, AE2_EN_OUT_DIR, AE2_ZH_OUT_DIR


# AE2 手册的翻译
def extract_ae2_markdown(mods_dir, en_output_dir):
    # 创建输出目录
    os.makedirs(en_output_dir, exist_ok=True)

    # 遍历 JAR 文件
    for zip_file in os.listdir(mods_dir):
        zip_path = os.path.join(mods_dir, zip_file)
        if not zip_path.endswith(".jar") and not zip_path.endswith(".zip"):
            continue

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 获取 ZIP 中所有文件名
                file_list = zip_ref.namelist()

                suffix = ".md"
                md_files = [f for f in file_list if fnmatch.fnmatch(f, f"assets/*/ae2guide/*{suffix}")]

                # 提取 en_us.lang 文件并转换为 JSON
                for md_file in md_files:
                    new_path = md_file.removeprefix("assets/")
                    if fnmatch.fnmatch(new_path, "*/ae2guide/_*"):
                        continue
                    output_path = os.path.join(en_output_dir, new_path)
                    output_dir_name = os.path.dirname(output_path)
                    os.makedirs(output_dir_name, exist_ok=True)
                    try:
                        with zip_ref.open(md_file) as src:
                            content = src.read().decode()  # 假设是 UTF-8 编码
                            with open(output_path, "w", encoding="utf-8") as dst:
                                dst.write(content)
                        print(f"提取 en: {md_file} -> {output_path}")
                    except Exception as e:
                        print(f"读取 en 文件时出错: {md_file}, 错误: {e}")
        except zipfile.BadZipFile:
            print(f"跳过损坏的 ZIP 文件: {zip_path}")
        except Exception as e:
            print(f"处理 ZIP 文件时出错: {zip_path}, 错误: {e}")

def translate_ae2_markdown(en_output_dir, zh_output_dir):
    def translate_worker(input_document, rel_path, output_file):
        dir_path = os.path.dirname(output_file)
        os.makedirs(dir_path, exist_ok=True)
        print(f"处理中: {rel_path}")
        zh_document = translate_document(input_document)
        print(f"处理完成: {rel_path}")
        print(zh_document)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(zh_document)
        return True

    with ThreadPoolExecutor(max_workers=12) as executor:
        total = 0
        finished = 0
        futures = []
        for root, paths, files in os.walk(en_output_dir):
            for file in files:
                total += 1
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, en_output_dir).replace(os.sep, '/').removeprefix('/')
                namespace = rel_path.split('/', 1)[0]
                file_path = rel_path.removeprefix(f'{namespace}/ae2guide/')
                zh_cn_file_path = os.path.join(zh_output_dir, f'{namespace}/ae2guide/_zh_cn', file_path)
                if os.path.exists(zh_cn_file_path):
                    finished += 1
                    continue
                zh_cn_dir_path = os.path.dirname(zh_cn_file_path)
                os.makedirs(zh_cn_dir_path, exist_ok=True)
                with open(full_path, 'r', encoding='utf-8') as f:
                    en_document = f.read()

                future = executor.submit(translate_worker, en_document, rel_path, zh_cn_file_path)
                futures.append(future)

        for future in as_completed(futures):
            result = future.result()
            finished += 1
            print(f'进度: {finished}/{total}')
            print()


if __name__ == '__main__':
    # 提取 AE2 手册的原文
    extract_ae2_markdown(MODS_DIR, AE2_EN_OUT_DIR)
    # 使用 AI 翻译
    translate_ae2_markdown(AE2_EN_OUT_DIR, AE2_ZH_OUT_DIR)