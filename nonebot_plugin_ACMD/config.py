from pydantic import BaseModel
from nonebot import get_plugin_config


class Config(BaseModel):
    similarity_rate: float = 75.0  # 相似度阈值，高于此值的命令才会被纠正


config = get_plugin_config(Config)