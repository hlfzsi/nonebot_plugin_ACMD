from pypinyin import lazy_pinyin, Style
from numba import njit, int32
import numpy as np
from typing import Dict, Tuple, List
from functools import lru_cache
import pandas as pd
KEYBOARD_LAYOUT: Dict[str, Tuple[float, float, float, float]] = {
    '¢': (0, 0, 0, 2),  # 保留字符，用于补齐
    '`': (-11.25, -6.5, 0.6, 2),
    '1': (-10.5, -5.0, 0.6, 2),
    '2': (-7.5, -5.0, 0.9, 2),
    '3': (-6.0, -5.0, 1.2, 2),
    '4': (-4.5, -5.0, 1.5, 2),
    '5': (-3.0, -5.0, 1.8, 2),
    '6': (-1.5, -5.0, 2.1, 2),
    '7': (0.0, -5.0, 2.4, 2),
    '8': (1.5, -5.0, 2.7, 2),
    '9': (3.0, -5.0, 3.0, 2),
    '0': (4.5, -5.0, 3.3, 2),
    '-': (6.0, -5.0, 3.6, 2),
    '=': (6.75, -5.0, 3.9, 2),
    'Q': (-7.5, -3.5, 1.2, 2),
    'W': (-6.375, -3.5, 1.5, 2),
    'E': (-4.875, -3.5, 1.8, 2),
    'R': (-3.375, -3.5, 2.1, 2),
    'T': (-1.875, -3.5, 2.4, 2),
    'Y': (0.625, -3.5, 2.7, 2),
    'U': (2.125, -3.5, 3.0, 2),
    'I': (3.625, -3.5, 3.3, 2),
    'O': (5.125, -3.5, 3.6, 2),
    'P': (6.625, -3.5, 3.9, 2),
    '[': (-9.75, -3.5, 0.9, 2),
    ']': (6.75, -3.5, 4.2, 2),
    '\\': (7.875, -3.5, 4.5, 2),
    'A': (-6.0, -2.0, 1.8, 2),
    'S': (-4.5, -2.0, 2.1, 2),
    'D': (-3.0, -2.0, 2.4, 2),
    'F': (-1.5, -2.0, 2.7, 2),
    'G': (0.0, -2.0, 3.0, 2),
    'H': (1.5, -2.0, 3.3, 2),
    'J': (3.0, -2.0, 3.6, 2),
    'K': (4.5, -2.0, 3.9, 2),
    'L': (6.0, -2.0, 4.2, 2),
    ';': (-6.0, -2.0, 1.5, 2),
    '\'': (-5.25, -1.625, 1.8, 2),
    'Z': (-4.125, -0.5, 2.4, 2),
    'X': (-2.625, -0.5, 2.7, 2),
    'C': (-0.625, -0.5, 3.0, 2),
    'V': (1.375, -0.5, 3.3, 2),
    'B': (-1.5, -0.5, 4.5, 2),
    'N': (1.375, -0.5, 4.8, 2),
    'M': (2.875, -0.5, 5.1, 2),
    ',': (-4.5, -0.5, 2.7, 2),
    '.': (-3.0, -0.5, 3.0, 2),
    '/': (-1.5, -0.5, 3.3, 2),
    ' ': (-1.5, 2.0, 4.5, 2),
    '!': (-7.5, -5.0, 0.6, 2),
    '@': (-6.0, -5.0, 0.9, 2),
    '#': (-4.5, -5.0, 1.2, 2),
    '$': (-3.0, -5.0, 1.5, 2),
    '%': (-1.5, -5.0, 1.8, 2),
    '^': (0.0, -5.0, 2.1, 2),
    '&': (1.5, -5.0, 2.4, 2),
    '*': (3.0, -5.0, 2.7, 2),
    '(': (4.5, -5.0, 3.0, 2),
    ')': (6.0, -5.0, 3.3, 2),
    '_': (7.5, -5.0, 3.6, 2),
    '+': (8.25, -5.0, 3.9, 2),
    '{': (-9.75, -3.5, 0.9, 2),
    '}': (6.75, -3.5, 4.2, 2),
    '|': (7.875, -3.5, 4.5, 2),
    ':': (-6.0, -2.0, 1.5, 2),
    '"': (-5.25, -1.625, 1.8, 2),
    '<': (-4.5, -0.5, 2.4, 2),
    '>': (-3.0, -0.5, 2.7, 2),
    '?': (-1.5, -0.5, 3.0, 2),
    '~': (-9.75, -5.0, 0.6, 2)
}

# 构建查找表
chars = list(KEYBOARD_LAYOUT.keys())
positions = [KEYBOARD_LAYOUT[char] for char in chars]
CHAR_CODES = np.array([ord(c) for c in chars], dtype=np.uint8)
POSITIONS = np.array(positions, dtype=np.float64)

# 创建一个从字符代码到索引的查找表，大小为256以覆盖所有可能的ASCII字符
MAX_CHAR_CODE = 256
LOOKUP_TABLE = np.full(MAX_CHAR_CODE, -1, dtype=np.int32)
for idx, char_code in enumerate(CHAR_CODES):
    if char_code < MAX_CHAR_CODE:
        LOOKUP_TABLE[char_code] = idx
del KEYBOARD_LAYOUT


# 辅助函数以获取字符位置
@njit(nogil=True)
def get_char_position(char_code):
    idx = LOOKUP_TABLE[char_code]
    if idx >= 0:
        return POSITIONS[idx]
    else:
        return np.array([0.0, 0.0, 0.0, 0.0])


def get_pinyin_with_tone_marks(text: str) -> list:
    result = []
    for p in lazy_pinyin(text, style=Style.TONE3):
        # 保留声母（如果是有的话）和最后一个字符（音标数字）
        if len(p) > 1 and p[0].isalpha():
            initial = p[0].upper()  # 声母大写
            tone = p[-1] if p[-1].isdigit() else ''  # 只取最后一位作为音标数字
            result.append(f"{initial}{tone}")
        elif p[-1].isdigit():  # 如果没有声母，只有韵母带音标
            result.append(p[-1])
        else:  # 没有音标数字则保持原样
            result.append(p.upper())
    return result


def preprocess_text(text: str, cycle_weights: list = [1.0, 0.7, 0.5], hanzi_weight: float = 2.0, punctuation_weight: float = 3.0) -> Tuple[str, np.ndarray]:
    """预处理文本，返回包含拼音的文本以及原始文本的位置权重，使用字典循环权重"""
    result = []
    weights = []

    for i, char in enumerate(text):
        weight = cycle_weights[i % len(cycle_weights)]
        if '\u4e00' <= char <= '\u9fff':  # 如果是汉字
            pinyin_with_tone = get_pinyin_with_tone_marks(char)
            result.extend(pinyin_with_tone)
            weight = hanzi_weight*weight
            weights.extend([weight] * len(pinyin_with_tone))
        elif not char.isalnum():  # 如果是非字母数字字符（标点符号等）
            result.append(char.upper())
            weight = punctuation_weight*weight
            weights.append(weight)
        else:
            result.append(char.upper())
            weights.append(weight)

    # 归一化权重
    total_weight = sum(weights)
    if total_weight != 0:
        weights = [w / total_weight for w in weights]

    return ''.join(result), np.array(weights, dtype=np.float64)


@lru_cache(maxsize=None)
def preprocess_text_cached(text: str, cycle_weights: tuple = (1.0, 0.7, 0.5), hanzi_weight: float = 2.0, punctuation_weight: float = 3.0) -> Tuple[str, np.ndarray]:
    return preprocess_text(text, cycle_weights, hanzi_weight, punctuation_weight)


@njit(fastmath=True, nogil=True)
def balanced_angle_magnitude_similarity(v1: np.ndarray, v2: np.ndarray, alpha: float = 0.73, decay_rate: float = 3.0) -> float:
    if np.linalg.norm(v1) == 0 and np.linalg.norm(v2) == 0:
        return 1.0
    elif np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0.0

    # 计算原始cos相似度，并裁剪到合法范围
    cos_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)
                                ) if np.linalg.norm(v1) != 0 and np.linalg.norm(v2) != 0 else 0.0
    cos_sim_clipped = min(max(cos_sim, 0.0), 1.0)  # 确保cos_sim在[0, 1]范围内

    # 指数衰减以增加角度敏感度
    cos_sim_transformed = np.exp(-decay_rate * (1 - cos_sim_clipped))

    magnitude_diff = (np.linalg.norm(v1 - v2) / max(np.linalg.norm(v1), np.linalg.norm(v2))
                      ) if np.linalg.norm(v1) != 0 and np.linalg.norm(v2) != 0 else 0.0
    magnitude_rate = 1 - magnitude_diff

    similarity_score = alpha * cos_sim_transformed + \
        (1 - alpha) * magnitude_rate

    return similarity_score if similarity_score <= 1.0 and similarity_score >= 0.0 else 0.0


@njit(fastmath=True, nogil=True)
def offset_penalty(pos1: np.ndarray, pos2: np.ndarray) -> float:
    penalties = np.array([0.9, 0.95, 0.85, 0.9])
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]

    # 使用np.sign得到dx和dy的方向，0, 1, 或 -1
    dir_x = np.sign(dx)
    dir_y = np.sign(dy)

    penalty = 1.0

    # 根据方向更新penalty，注意当dir_x或dir_y为0时，不应用惩罚
    if dir_x != 0:
        penalty *= penalties[0 if dir_x > 0 else 1]  # right or left
    if dir_y != 0:
        penalty *= penalties[2 if dir_y > 0 else 3]  # down or up

    return penalty


@njit(fastmath=True, nogil=True)
def calculate_adjusted_vector(text: List[str], weights: np.ndarray) -> np.ndarray:
    vector = np.zeros(4)
    prev_pos = np.array([0.0, 0.0, 0.0, 0.0])
    for i in range(len(text)):
        char_code = ord(text[i])
        pos = get_char_position(char_code)
        if pos[0] != 0 or pos[1] != 0 or pos[2] != 0 or pos[3] != 0:  # 如果有有效的键盘位置
            penalty = offset_penalty(prev_pos, pos)
            vector += pos * weights[i] * penalty
            prev_pos = pos
    return vector


@njit(fastmath=True, nogil=True)
def align_sequences(seq1: str, seq2: str) -> Tuple[List[str], List[str]]:
    max_len = max(len(seq1), len(seq2))
    seq1_padded = seq1.ljust(max_len, '¢')
    seq2_padded = seq2.ljust(max_len, '¢')

    m, n = len(seq1_padded), len(seq2_padded)
    max_dist = m + n

    dp = np.full((m + 1, n + 1), max_dist, dtype=int32)

    for i in range(m + 1):
        dp[i, 0] = i
    for j in range(n + 1):
        dp[0, j] = j

    for d in range(m + n + 1):
        start_i = max(0, d - n)
        end_i = min(d, m)
        for i in range(start_i, end_i + 1):
            j = d - i
            if i > 0 and j > 0:
                cost = int32(
                    0) if seq1_padded[i - 1] == seq2_padded[j - 1] else int32(1)
                dp[i, j] = min(dp[i - 1, j] + 1, dp[i, j - 1] +
                               1, dp[i - 1, j - 1] + cost)

    aligned_seq1 = [''] * max_len
    aligned_seq2 = [''] * max_len
    i, j = m, n
    k = max_len - 1

    while i > 0 or j > 0:
        if i > 0 and j > 0 and ((seq1_padded[i - 1] == seq2_padded[j - 1]) or (dp[i, j] == dp[i - 1, j - 1] + (seq1_padded[i - 1] != seq2_padded[j - 1]))):
            aligned_seq1[k] = seq1_padded[i - 1]
            aligned_seq2[k] = seq2_padded[j - 1]
            i -= 1
            j -= 1
        elif i > 0 and (dp[i, j] == dp[i - 1, j] + 1):
            aligned_seq1[k] = seq1_padded[i - 1]
            aligned_seq2[k] = '¢'
            i -= 1
        elif j > 0 and (dp[i, j] == dp[i, j - 1] + 1):
            aligned_seq1[k] = '¢'
            aligned_seq2[k] = seq2_padded[j - 1]
            j -= 1
        k -= 1
    return aligned_seq1, aligned_seq2


def similarity(str1: str, str2: str) -> float:
    if str1.endswith('~'):
        str1 = str1.rstrip('~')
        str2 = str2[:len(str1)]
        if len(str2) < len(str1):
            return 0.0
        if str1 == str2:
            return 1.0
    else:
        if len(str1) >= 2*len(str2) or len(str1) <= 0.5*len(str2):
            return 0.0

    # 预处理文本
    processed_str1, weights_str1 = preprocess_text(str1)
    processed_str2, weights_str2 = preprocess_text_cached(str2)
    if not processed_str1 or not processed_str2:
        return 0.0

    # 对齐序列
    aligned_seq1, aligned_seq2 = align_sequences(
        processed_str1, processed_str2)

    # 计算加权向量
    vec1 = calculate_adjusted_vector(aligned_seq1, weights_str1)
    vec2 = calculate_adjusted_vector(aligned_seq2, weights_str2)

    # 使用平衡夹角-模长相似度计算
    return balanced_angle_magnitude_similarity(vec1, vec2)


def similarity_for_df(df: pd.DataFrame, user_input: str) -> pd.DataFrame:
    """
    计算用户输入与DataFrame中每个命令的相似度，并返回包含相似度分数的新DataFrame。

    参数:
        df (pd.DataFrame): 包含命令及相关信息的DataFrame。
        user_input (str): 用户输入的字符串。

    返回:
        pd.DataFrame: 包含原始列和新列'similarity'的DataFrame。
    """
    # 创建一个新的DataFrame用于存储结果
    df_with_similarity = df.copy()

    if df_with_similarity.empty:
        return df_with_similarity

    # 获取消息的前N个单词
    message_split = user_input.split(' ')

    # 初始化相似度列为0
    df_with_similarity['similarity'] = 0.0

    def calculate_similarity(command: str, user_input_part: str) -> float:
        """内部函数，用于计算单个命令与用户输入的相似度"""
        if user_input_part.endswith('~'):
            user_input_part = user_input_part.rstrip('~')
            command = command[:len(user_input_part)]
            if len(command) < len(user_input_part):
                return 0.0
            if user_input_part == command:
                return 1.0
        else:
            if len(user_input_part) >= 2 * len(command) or len(user_input_part) <= 0.5 * len(command):
                return 0.0

        # 利用缓存的预处理结果
        processed_command, weights_command = preprocess_text_cached(command)
        if not processed_command:
            return 0.0

        # 对齐序列
        aligned_seq1, aligned_seq2 = align_sequences(
            processed_user_input, processed_command)

        # 计算加权向量
        vec1 = calculate_adjusted_vector(aligned_seq1, weights_user_input)
        vec2 = calculate_adjusted_vector(aligned_seq2, weights_command)

        # 使用平衡夹角-模长相似度计算
        return balanced_angle_magnitude_similarity(vec1, vec2)

    # 根据 command_spaces 分类处理
    for spaces in df_with_similarity['command_spaces'].unique():
        filtered_df: pd.DataFrame = df_with_similarity[df_with_similarity['command_spaces'] == spaces].copy(
        )
        if not filtered_df.empty:
            # 截取用户输入的一部分
            user_input_part = ' '.join(message_split[:spaces + 1])
            processed_user_input, weights_user_input = preprocess_text(
                user_input_part)

            # 应用相似度计算函数到每一行
            filtered_df['similarity'] = filtered_df['command'].apply(
                lambda command: calculate_similarity(command, user_input_part)
            )

            # 更新原 DataFrame 的相似度列
            df_with_similarity.loc[filtered_df.index,
                                   'similarity'] = filtered_df['similarity']

    return df_with_similarity


# 示例测试用例
if __name__ == "__main__":
    import time
    test_cases = [
        ("你好去", "你好啊哇"),
        ("abc", "abcd"),
        ("hello", "hallo"),
        ("test", "tset"),
        ("same", "same"),
        ('shit', 'qqqq'),
        ("fuc~", "fuck"),
        ("happy", "good"),
        ("recent", "rezrt"),
        ("111", "535")
    ]

    for str1, str2 in test_cases:
        print(f"Similarity between {str1} {str2} : {similarity(str1, str2)}")

    t = time.time()
    for i in range(1000):
        for str1, str2 in test_cases:
            similarity(str1, str2)
    print(f"Execution time for 1000 iterations over test cases: {
          time.time()-t:.6f} seconds")

    # 创建测试 DataFrame
    data = {
        'command': [
            'open file',
            'save document',
            'edit mode',
            'delete line',
            'undo changes',
            'redo actions',
            'search term',
            'replace word',
            'copy selection',
            'paste content',
            'recent'
        ],
        'description': [
            'Open a file.',
            'Save the current document without prompting.',
            'Enter edit mode.',
            'Delete the current line.',
            'Undo the last change.',
            'Redo the last undone action.',
            'Search for a specific term in the document.',
            'Replace a specific word with another word.',
            'Copy the selected text to clipboard.',
            'Paste the copied content at the cursor position.',
            '1'
        ],
        'command_spaces': [1, 2, 1, 2, 2, 2, 2, 2, 2, 2, 0]
    }

    df_test = pd.DataFrame(data)

    # 准备用户输入列表
    user_inputs = [
        'open f',
        'save d~',
        'edi m',
        'del l',
        'und c',
        'red a',
        'sea t',
        'rep w',
        'cop s',
        'pas c',
        'open file',
        'save document',
        'edit mode',
        'delete line',
        'undo changes',
        'redo actions',
        'search term',
        'replace word',
        'copy selection',
        'paste content',
        'recnt',
        'rezrt'
    ]

    # 测试 similarity_for_df 函数
    for user_input in user_inputs:
        result_df = similarity_for_df(df_test, user_input)
        print(f"User Input: '{user_input}'")
        print(result_df[['command', 'similarity']])
        print("\n" + "-"*80 + "\n")
