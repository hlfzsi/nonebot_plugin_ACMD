import threading
from typing import Any, Optional, Union
from abc import ABC, abstractmethod, ABCMeta
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot import logger
from typing import Any, Optional
import inspect
import os
from weakref import WeakValueDictionary
from collections import defaultdict


class SingletonABCMeta(ABCMeta):
    _instances: WeakValueDictionary = WeakValueDictionary()
    _lock: threading.Lock = threading.Lock()
    _path_instances: defaultdict = defaultdict(WeakValueDictionary)

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    # 获取创建实例的脚本文件夹的绝对路径
                    if 'script_folder_path' not in kwargs:
                        caller_frame = inspect.stack()[1]
                        caller_filename = caller_frame.filename
                        script_folder_path = os.path.abspath(
                            os.path.dirname(caller_filename))
                    else:
                        script_folder_path = kwargs.pop('script_folder_path')

                    # 创建实例
                    instance = super(SingletonABCMeta, cls).__call__(
                        *args, **kwargs)
                    cls._instances[cls] = instance

                    # 将实例的弱引用添加到路径实例字典中
                    cls._path_instances[script_folder_path][instance] = instance

                    # 日志记录
                    if not isinstance(instance, BasicHandler):
                        logger.warning(
                            f'实例 {instance} 不是 BasicHandler 子类, 这很可能会导致未知错误')
                    try:
                        logger.info(f'成功注册处理ID为 {instance.handler_id} 的实例 {
                                    str(instance)}')
                    except AttributeError:
                        logger.info(f'成功注册处理实例 {instance}')

        return cls._instances[cls]


class BasicHandler(ABC, metaclass=SingletonABCMeta):
    """处理器基类

    - 必须实现异步方法 handle

    - 属性:
        - block (bool): 是否阻断传播,默认为True
        - handler_id (int): 处理器ID,由HandlerManager自动分配
        - unique (str): 处理器唯一标识符,可用于测试辨识,默认为None

    - 可使用的方法:
        - is_PrivateMessageEvent 判断当前消息事件是否为私聊消息
        - get_self_id 获取当前处理器实例的处理ID
        - get_handler_by_id 通过处理ID获取处理器实例
        - get_handler_id 通过处理器实例获取处理ID


    - 推荐重写方法 (按执行顺序排列) :
        - should_handle 异步  该处理器是否应当执行 , 必须返回bool
        - should_block 异步  该处理器是否阻断传播 , 必须返回bool
    """
    __slots__ = ('block', '_handler_id', 'unique', '__weakref__')

    def __init__(self, block: bool = True, unique: str = None, **kwargs):
        self.block = block
        self._handler_id: int = HandlerManager.get_id(self)
        self.unique = unique

    @abstractmethod
    async def handle(self, bot: Bot = None, event: Union[GroupMessageEvent, PrivateMessageEvent] = None, msg: str = None, qq: str = None, groupid: str = None, image: Optional[str] = None, ** kwargs: Any) -> None:
        """处理接收到的消息。

        参数:
            bot (Bot): 机器人实例
            event (Union[GroupMessageEvent, PrivateMessageEvent]): 消息事件
            msg (str): 处理后的消息文本
            qq (str): 发送者的QQ号
            groupid (str): 群组ID（私聊时为 -1 ）
            image (Optional[str]): 图片URL（如果有,且最多一张）
            **kwargs (BasicHandler): 其他关键字参数
        """
        pass

    @staticmethod
    def is_PrivateMessageEvent(event: Union[GroupMessageEvent, PrivateMessageEvent]):
        return event.message_type == 'private'

    async def should_handle(self, ** kwargs: Any) -> bool:
        return True

    async def should_block(self, ** kwargs: Any) -> bool:
        return self.block

    def get_self_id(self) -> int:
        return self.handler_id

    @staticmethod
    def get_handler_by_id(handler_id: int) -> Optional['BasicHandler']:
        return HandlerManager.get_handler(handler_id)

    @staticmethod
    def get_handler_id(handler: 'BasicHandler') -> int:
        return HandlerManager.get_id(handler)

    @property
    def handler_id(self) -> int:
        return self._handler_id

    def remove(self):
        HandlerManager.remove_handler(self)
        with SingletonABCMeta._lock:
            if type(self) in SingletonABCMeta._instances and SingletonABCMeta._instances[type(self)] is self:
                del SingletonABCMeta._instances[type(self)]


    def __str__(self):
        if self.unique:
            return f'{self.unique}'
        else:
            return f'{self.__class__.__name__}'


class HandlerManager:
    _id_to_handler: dict[int, BasicHandler] = {}
    _handler_to_id: dict[BasicHandler, int] = {}
    _next_id: int = 1
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_id(cls, handler: BasicHandler) -> int:
        if handler in cls._handler_to_id:
            return cls._handler_to_id[handler]

        with cls._lock:
            if handler in cls._handler_to_id:
                return cls._handler_to_id[handler]

            new_id = cls._next_id
            cls._id_to_handler[new_id] = handler
            cls._handler_to_id[handler] = new_id
            cls._next_id += 1

            return new_id

    @classmethod
    def get_handler(cls, id: int) -> Optional[BasicHandler]:
        return cls._id_to_handler.get(id)

    @classmethod
    def remove_handler(cls, handler: BasicHandler) -> bool:
        with cls._lock:
            if handler in cls._handler_to_id:
                handler_id = cls._handler_to_id.pop(handler)
                del cls._id_to_handler[handler_id]
                logger.info(f'处理ID为  {handler_id}  的实例  {str(handler)}  已注销')


if __name__ == '__main__':
    class HandlerA(BasicHandler):
        async def handle(self, bot: Bot, event: GroupMessageEvent | PrivateMessageEvent, msg: str, qq: str, groupid: str, image: str | None, **kwargs: Any) -> None:
            print(f'{self.handler_id} and Handler is running')

    print(HandlerA().handler_id)
    print(HandlerA().handler_id)

    print(HandlerA().handler_id)
    B = HandlerA(False)
    print(f'{BasicHandler.get_handler_by_id(1)}')
    print(B.handler_id)
    print(f'{SingletonABCMeta._instances}')
