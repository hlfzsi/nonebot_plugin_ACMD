from pydantic import BaseModel


class Config(BaseModel):
    Similarity_Rate: float = 75.0  # 相似度阈值，高于此值的命令才会被纠正


config = Config()
