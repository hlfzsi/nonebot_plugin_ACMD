import sqlite3
from nonebot import logger
import pandas as pd
from .connection_pool import SQLitePool
from nonebot.exception import StopPropagation
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from typing import List, Union, Any, Optional, Dict, Callable
import asyncio
from collections import Counter

SHARED_MEMORY_DB_NAME = "file:shared_memory_db?mode=memory&cache=shared"
MEMORY_DB_CONN = sqlite3.connect(SHARED_MEMORY_DB_NAME, uri=True)
COMMAND_POOL = SQLitePool(shared_uri=SHARED_MEMORY_DB_NAME)

from .command_signer import BasicHandler  # noqa


def create_memory_table():
    cursor = MEMORY_DB_CONN.cursor()

    # 创建 commands 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commands (
            command TEXT PRIMARY KEY,
            description TEXT,
            owner TEXT,
            full_match INTEGER,
            handler_list TEXT  -- 使用逗号分隔的字符串来存储多个 Handler 的 ID
        )
    ''')
    # 创建 helps 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS helps (
            owner TEXT PRIMARY KEY,
            help TEXT,
            function BOOLEAN DEFAULT 0
        )
    ''')

    # 创建索引以提高查询性能
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_owners ON commands(owner)
    ''')

    MEMORY_DB_CONN.commit()


create_memory_table()


class CommandData:
    """数据模型类，用于存储命令的属性。"""

    def __init__(self, command: List[str], description: str, owner: str, full_match: bool, handler_list: List[str]):
        self.command = command
        self.description = description
        self.owner = owner
        self.full_match = full_match
        self.handler_list = handler_list


class CommandDatabase:
    """数据库操作类，用于命令的增删改查。"""

    def __init__(self, db_connection: sqlite3.Connection = None):
        self.conn = db_connection

    def insert_commands(self, command_data: CommandData):
        """插入命令到数据库。"""
        cursor = self.conn.cursor()
        cursor.executemany('''
            INSERT INTO commands (command, description, owner, full_match, handler_list)
            VALUES (?, ?, ?, ?, ?)
        ''', [(cmd, command_data.description, command_data.owner, command_data.full_match, ','.join(command_data.handler_list)) for cmd in command_data.command])
        self.conn.commit()

    async def update_commands(self, command_data: CommandData):
        """更新命令到数据库。"""
        async with COMMAND_POOL.connection() as conn:
            try:
                conn.isolation_level = 'EXCLUSIVE'
                cursor = await conn.cursor()
                await cursor.execute('BEGIN EXCLUSIVE')
                await cursor.executemany('''
                    INSERT OR REPLACE INTO commands (command, description, owner, full_match, handler_list)
                    VALUES (?, ?, ?, ?, ?)
                ''', [(cmd, command_data.description, command_data.owner, command_data.full_match, ','.join(command_data.handler_list)) for cmd in command_data.command])
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                raise e

    async def remove_commands(self, commands: List[str]):
        """删除命令记录。"""
        async with COMMAND_POOL.connection() as conn:
            cursor = await conn.cursor()
            await cursor.executemany('DELETE FROM commands WHERE command = ?', [(cmd,) for cmd in commands])
            await conn.commit()

    async def get_commands(self, command: str):
        """获取命令记录。"""
        async with COMMAND_POOL.connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute('SELECT * FROM commands WHERE command = ?', (command,))
            return await cursor.fetchone()


class Command:
    """命令类。"""

    def __init__(self, commands: List[str], description: str, owner: str, full_match: bool, handler_list: List[Union[str, BasicHandler]]):
        self.data = CommandData(
            command=list(dict.fromkeys([command.strip()
                         for command in commands])),
            description=description,
            owner=owner,
            full_match=full_match,
            handler_list=[str(handler.handler_id) if isinstance(
                handler, BasicHandler) else handler for handler in handler_list]
        )

        # 在初始化时进行验证和保存
        if self.validate():
            self.save()

    def validate(self) -> bool:
        """验证命令数据的合法性。"""
        for command in self.data.command:
            if not command or not isinstance(command, str) or (command == '/help' and self.data.owner != 'origin'):
                return False
        return True

    def save(self):
        """保存命令数据到数据库。"""
        if not self.validate():
            raise ValueError("Invalid command data.")

        db = CommandDatabase(MEMORY_DB_CONN)
        db.insert_commands(self.data)

    async def update(self, new_commands: List[str] = None, new_hander_list: List[Union[str, BasicHandler]] = None):
        db = CommandDatabase()
        if new_commands is not None:
            await db.remove_commands(self.data.command)
            self.data.command = list(dict.fromkeys(
                [command.strip() for command in new_commands]))
        if new_hander_list is not None:
            self.data.handler_list = [str(handler.handler_id) if isinstance(
                handler, BasicHandler) else handler for handler in new_hander_list]
        """更新命令数据到数据库。"""
        if not self.validate():
            raise ValueError("Invalid command data.")

        await db.update_commands(self.data)

    async def delete(self):
        """删除该命令。"""
        db = CommandDatabase()
        await db.remove_commands(self.data.command)


class CommandFactory:
    @staticmethod
    def create_command(commands: List[str], handler_list: List[Union[str, BasicHandler]], owner: str, description: str = '', full_match: bool = False) -> Command:
        """创建命令对象。

        Args:
            commands (List[str]):命令列表
            handler_list (List[Union[str, BasicHandler]]):处理器列表
            owner (str):所有者,用于标识指令所属插件
            description (str, optional): 描述. Defaults to ''.
            full_match (bool, optional): 是否完全匹配. Defaults to False.

        Returns:
            Command: 命令对象
        """
        return Command(commands, description, owner, full_match, handler_list)

    @staticmethod
    def create_help_command(owner: str, help_text: str = '', function: Callable = None) -> None:
        """接管帮助命令。

        Args:
            owner (str): 被接管插件对象
            help_text (str): 帮助文本
            function (Callable, optional): 帮助命令处理函数. Defaults to None.可返回字符串,也可返回None

            通常情况下,help_text与function选择一个传入即可,function优先级更高.
        """
        HelpTakeOverManager.takeover_help(owner, help_text, function)


class HelpTakeOverManager:
    """帮助接管管理器。"""
    _owner_to_function: Dict[str, Callable] = {}

    @classmethod
    def takeover_help(cls, owner: str, help_text: str = '', function: Callable = None) -> None:
        """接管帮助命令。"""
        is_function = False
        if owner in cls._owner_to_function:
            raise ValueError(f"Help command of {
                             owner} has already taken over.")
        if not help_text and not function and owner != 'origin':
            raise ValueError(
                "Either help_text or function should be provided.")
        if function and callable(function) and asyncio.iscoroutinefunction(function):
            cls._owner_to_function[owner] = function
            is_function = True
        elif function:
            raise ValueError(
                "function should be an asynchronous function (i.e., defined with 'async def').")

        if not is_function:
            with MEMORY_DB_CONN as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO helps (owner, help, function) VALUES (?, ?, ?)', (owner, help_text, 0))
                conn.commit()
        else:
            with MEMORY_DB_CONN as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO helps (owner, help, function) VALUES (?, ?, ?)', (owner, help_text, 1))
                conn.commit()

    @classmethod
    def get_function(cls, owner: str):
        if owner in cls._owner_to_function:
            return cls._owner_to_function[owner]


def _ngram_similarity(s1: str, s2: str, n: int = 2) -> float:
    """计算两个字符串之间的n-gram相似度。"""
    grams1 = Counter(_ngrams(s1.lower(), n))
    grams2 = Counter(_ngrams(s2.lower(), n))
    intersection = grams1 & grams2
    union = grams1 | grams2
    return sum(intersection.values()) / sum(union.values()) if union else 0.0


def _ngrams(text: str, n: int = 2) -> List[str]:
    """从给定文本生成n-gram计数。"""
    return [text[i:i+n] for i in range(len(text)-n+1)]


async def dispatch(
    message: str,
    bot: Bot,
    event: Union[GroupMessageEvent, PrivateMessageEvent],
    image: Optional[str] = None,
    private_vars: Optional[Dict[str, Any]] = None
) -> None:
    """消息派发，执行对应逻辑"""

    groupid: str = str(getattr(event, 'group_id', -1))
    message = message.strip()
    if not message:
        return

    async with COMMAND_POOL.connection() as conn:
        cursor = await conn.cursor()
        try:
            if len(message) < 2:
                await cursor.execute('SELECT command, handler_list FROM commands WHERE command = ?', (message,))
            else:
                prefix = message[:2]
                await cursor.execute('SELECT command, handler_list, full_match FROM commands WHERE command = ? OR command LIKE ?', (message, f'{prefix}%'))
            commands = await cursor.fetchall()
        except Exception as e:
            # 记录错误信息
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            await cursor.close()

    if not commands:
        return

    df_commands = pd.DataFrame(
        commands, columns=['command', 'handler_list', 'full_match'])
    best_match, best_match_handlers, exact_match, highest_similarity = None, [], False, 0.0

    # 检查完全匹配
    exact_matches = df_commands[df_commands['command'] == message]
    if not exact_matches.empty:
        best_match = exact_matches.iloc[0]['command']
        best_match_handlers = exact_matches.iloc[0]['handler_list'].split(',')
        exact_match = True
    else:
        # 计算命令的空格数量
        df_commands['command_spaces'] = df_commands['command'].str.count(' ')

        # 获取消息的前N个单词
        message_split = message.split(' ')

        # 查找非完全匹配命令
        df_commands['message_n_plus_1_space_content'] = df_commands['command_spaces'].apply(
            lambda spaces: ' '.join(
                message_split[:spaces + 1]) if spaces + 1 <= len(message_split) else ''
        )

        matches = df_commands[(~df_commands['full_match']) & (
            df_commands['command'] == df_commands['message_n_plus_1_space_content'])]
        if not matches.empty:
            best_match = matches.iloc[0]['command']
            best_match_handlers = matches.iloc[0]['handler_list'].split(',')
            exact_match = True

        # 计算相似度
        if not df_commands.empty and not exact_match:
            df_commands['similarity'] = df_commands.apply(
                lambda row: _ngram_similarity(
                    row['message_n_plus_1_space_content'], row['command'])
                if row['command_spaces'] + 1 <= len(message_split) else 0.0, axis=1
            )

            # 找到相似度最高的行
            max_similarity = df_commands['similarity'].max()
            best_match_rows = df_commands[df_commands['similarity']
                                          == max_similarity]
            if len(best_match_rows) == 1 and max_similarity >= 0.55:
                best_match_row = best_match_rows.iloc[0]
                best_match = best_match_row['command']
                best_match_handlers = best_match_row['handler_list'].split(',')
                highest_similarity = best_match_row['similarity']
                logger.debug(f"相似度最高的命令是：{best_match_rows.iloc[0]['command']}, 相似度为：{
                             max_similarity}")
            else:
                logger.debug(f"相似度最高的命令是：{best_match_rows.iloc[0]['command']}, 相似度为：{
                             max_similarity}")
                return

    # 确保字符数差异符合要求
    if best_match:
        command_full_match = df_commands[df_commands['command']
                                         == best_match]['full_match'].iloc[0]
        if command_full_match and abs(len(message) - len(best_match)) >= 1:
            return

        # 替换消息内容
        if not exact_match:
            message_parts = message.split(' ')
            command_spaces = best_match.count(' ')
            if command_spaces + 1 <= len(message_parts):
                message_parts[:command_spaces + 1] = best_match.split(' ')
                message = ' '.join(message_parts)

    # 继续执行处理程序
    if best_match:
        for handler_id in best_match_handlers:
            handler = BasicHandler.get_handler_by_id(int(handler_id))
            if handler:
                if await handler.should_handle(msg=message, image=image, qq=str(event.user_id), groupid=groupid, bot=bot, event=event, highest_similarity=highest_similarity, best_match_handlers=best_match_handlers):
                    asyncio.create_task(handler.handle(msg=message, image=image, qq=str(
                        event.user_id), groupid=groupid, bot=bot, event=event, best_match_handlers=best_match_handlers, **(private_vars or {})))
                    if await handler.should_block(msg=message, image=image, qq=str(event.user_id), groupid=groupid, bot=bot, event=event, highest_similarity=highest_similarity, best_match_handlers=best_match_handlers):
                        raise StopPropagation


class Helper(BasicHandler):
    __slots__ = BasicHandler.__slots__

    async def get_unique_owners(self):
        async with COMMAND_POOL.connection() as db:
            async with db.cursor() as cursor:
                await cursor.execute('SELECT DISTINCT owner FROM commands')
                owners = await cursor.fetchall()
                return [owner[0] for owner in owners if owner[0] != 'origin']

    async def get_owner_help(self, owner: str, page_cut: Union[int, str] = 1, **kwargs: Any):
        page_cut = int(page_cut)
        offset = (page_cut - 1) * 7

        async with COMMAND_POOL.connection() as db:
            query = """
                SELECT 'help' AS type, help AS content, function AS is_function FROM helps WHERE owner=?
                UNION ALL
                SELECT 'command' AS type, command AS content, description AS is_function FROM commands WHERE owner=? LIMIT ? OFFSET ?
                """

            async with db.execute(query, (owner, owner, 7, offset)) as cursor:
                results = await cursor.fetchall()

                if results:
                    # 检查是否有 helps 表的结果
                    for result in results:
                        if result[0] == 'help':
                            if result[2]:  # 检查 function 是否为 True
                                if HelpTakeOverManager.get_function(owner):
                                    func = HelpTakeOverManager.get_function(
                                        owner)
                                    # 调用异步函数并返回结果
                                    return await func(kwargs)
                            else:
                                return result[1]  # 返回 help 内容

                    # 如果没有 helps 表的结果，返回 commands 表的结果
                    formatted_results = '\n'.join(
                        [f"{cmd} : {desc}" if desc else f"{cmd}" for _,
                            cmd, desc in results if _ == 'command']
                    )
                    return formatted_results
                else:
                    return []

    async def handle(self, bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, msg: str, qq: str, groupid: str, image: str | None, **kwargs: Any) -> None:
        groups = msg.replace('/help ', '', 1).split(' ')
        if not groups or msg == '/help':
            msg_to_send = '\n'.join(await self.get_unique_owners())
        else:
            msg_to_send = await self.get_owner_help(groups[0], groups[1] if len(groups) == 2 else 1, bot=bot, event=event, msg=msg, qq=qq, groupid=groupid, image=image, extra_kwargs=kwargs)
        if msg_to_send:
            await bot.send(event=event, message=f'可用指令:\n{msg_to_send}')


CommandFactory.create_command(
    commands=['/help'],
    handler_list=[Helper(unique='origin_helper')],
    owner='origin',
    description='生成帮助文档'
)

if __name__ == '__main__':
    class HandlerA(BasicHandler):
        async def handle(self, bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, msg: str, qq: str, groupid: str, image: str | None, **kwargs: Any) -> None:
            print(f'{self.handler_id} and Handler is running')
    CommandFactory.create_command(
        ['/ChangeGtype', '/ChangeCtype'], 'test command', 'test', False, [HandlerA()])

    async def test():
        await dispatch('/Changetype 1', None, None)
    asyncio.run(test())
