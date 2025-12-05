from modelscope import snapshot_download

# 指定模型下载到当前目录下的 models 文件夹中
model_dir = snapshot_download('opendatalab/PDF-Extract-Kit', cache_dir='./models')

print(f"模型已下载到: {model_dir}")