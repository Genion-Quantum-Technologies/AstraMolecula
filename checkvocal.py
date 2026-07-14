import pickle
import sys
import json

sys.path.append('/home/songyou/projects/aidd-platform-workspace/apps/AstraMocula/AstraMolecula/src')
# 将 preprocess 所在的父目录（即 ml 文件夹）添加到 sys.path
sys.path.append('/home/songyou/projects/aidd-platform-workspace/apps/AstraMocula/AstraMolecula/src/astra_molecula/ml')
# 使用 'rb' (read binary) 模式读取文件
file_path = '/home/songyou/projects/aidd-platform-workspace/apps/AstraMocula/AstraMolecula/resource/vocab.pkl'

with open(file_path, 'rb') as f:
    vocab = pickle.load(f)

print(f"读取成功！词表大小: {len(vocab)}")

# 获取内部的双向字典
tokens_data = vocab._tokens

# 1. 过滤出一个干净的“词 -> 索引”字典 (只保留键是字符串的项)
token_to_id = {k: v for k, v in tokens_data.items() if isinstance(k, str)}

# 2. 导出为 JSON 文件 (最推荐，Python和其他语言都好读取)
json_path = 'vocab.json'
with open(json_path, 'w', encoding='utf-8') as jf:
    json.dump(token_to_id, jf, indent=4, ensure_ascii=False)
print(f"✅ 成功导出字典到: {json_path}")

# 3. 导出为 TXT 文件 (纯文本，方便你肉眼浏览，每行一个词)
txt_path = 'vocab.txt'
# 根据 ID 排序，保证导出的顺序是从 0 到 919
sorted_tokens = sorted(token_to_id.items(), key=lambda x: x[1])

with open(txt_path, 'w', encoding='utf-8') as tf:
    for word, index in sorted_tokens:
        tf.write(f"{index}\t{word}\n")
print(f"✅ 成功导出手册到: {txt_path}")