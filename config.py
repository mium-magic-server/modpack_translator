# 整合包模组路径
MODS_DIR = '/home/yourname/.minecraft/mods'
# 整合包版本文件路径
VERSION_JSON = '/home/yourname/.minecraft/versions/1.21.1/1.21.1.json'
WORK_DIR = 'work'
EN_OUT_DIR = WORK_DIR + '/en'
ZH_OUT_DIR = WORK_DIR + '/zh'
MERGED_EN_FILE = WORK_DIR + '/merged/merged_output_en.json'
MERGED_ZH_FILE = WORK_DIR + '/merged/merged_output_zh.json'
MERGED_MAP_FILE = WORK_DIR + '/merged/merged_en2zh.json'
AE2_EN_OUT_DIR = WORK_DIR + '/ae2/en'
AE2_ZH_OUT_DIR = WORK_DIR + '/ae2/zh'
CFPA_PATH = WORK_DIR + '/Minecraft-Mod-Language-Package'
CFPA_PROJECT_VERSION = '1.21'

# AI 大模型配置
openai_embed_base_url = ""
openai_llm_base_url = ""
openai_embed_model = "gte-multilingual-base"
openai_llm_model = "gpt4o"
openai_api_key = ""