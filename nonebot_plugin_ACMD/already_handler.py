from abc import abstractmethod
from typing import Callable, Type, Coroutine, Union, Optional, Any
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
import inspect
import os
from .command_signer import BasicHandler, SingletonABCMeta


class MessageHandler(BasicHandler):
    __slots__ = tuple(
        slot for slot in BasicHandler.__slots__ if slot != '__weakref__')

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


class GroupMessageHandler(BasicHandler):
    __slots__ = tuple(
        slot for slot in BasicHandler.__slots__ if slot != '__weakref__')

    @abstractmethod
    async def handle(self, bot: Bot = None, event: GroupMessageEvent = None, msg: str = None, qq: str = None, groupid: str = None, image: Optional[str] = None, ** kwargs: Any) -> None:
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

    async def should_handle(self, **kwargs):
        if 'event' in kwargs:
            return not self.is_PrivateMessageEvent(kwargs['event'])
        else:
            raise ValueError("Missing event")


class PrivateMessageHandler(BasicHandler):
    __slots__ = tuple(
        slot for slot in BasicHandler.__slots__ if slot != '__weakref__')

    @abstractmethod
    async def handle(self, bot: Bot = None, event:  PrivateMessageEvent = None, msg: str = None, qq: str = None, groupid: str = None, image: Optional[str] = None, ** kwargs: Any) -> None:
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

    async def should_handle(self, **kwargs):
        if 'event' in kwargs:
            return self.is_PrivateMessageEvent(kwargs['event'])
        else:
            raise ValueError("Missing event")


class func_to_Handler:
    @classmethod
    def message_handler(cls, handler_class: Type[BasicHandler], block: bool = True, unique: str = None) -> Callable[[Callable[..., Coroutine]], BasicHandler]:
        """
        装饰器，将一个异步函数转换为指定类型的处理器实例。

        :param handler_class: 处理器类，如 MessageHandler, GroupMessageHandler, PrivateMessageHandler
        :param block: 是否阻塞，默认为 True
        :param unique: 唯一标识符，默认为 None
        :return: 装饰器函数
        """
        return cls._create_decorator(handler_class, block, unique)

    @classmethod
    def all_message_handler(cls, block: bool = True, unique: str = None) -> Callable[[Callable[..., Coroutine]], BasicHandler]:
        """
        装饰器，将一个异步函数转换为指定类型的处理器实例。

        :param block: 是否阻塞，默认为 True
        :param unique: 唯一标识符，默认为 None
        :return: 装饰器函数
        """
        return cls._create_decorator(MessageHandler, block, unique)

    @classmethod
    def group_message_handler(cls, block: bool = True, unique: str = None) -> Callable[[Callable[..., Coroutine]], GroupMessageHandler]:
        """
        装饰器，将一个异步函数转换为 GroupMessageHandler 实例。

        :param block: 是否阻塞，默认为 True
        :param unique: 唯一标识符，默认为 None
        :return: 装饰器函数
        """
        return cls._create_decorator(GroupMessageHandler, block, unique)

    @classmethod
    def private_message_handler(cls, block: bool = True, unique: str = None) -> Callable[[Callable[..., Coroutine]], PrivateMessageHandler]:
        """
        装饰器，将一个异步函数转换为 PrivateMessageHandler 实例。

        :param block: 是否阻塞，默认为 True
        :param unique: 唯一标识符，默认为 None
        :return: 装饰器函数
        """
        return cls._create_decorator(PrivateMessageHandler, block, unique)

    @classmethod
    def _create_decorator(cls, handler_class: Type[BasicHandler], block: bool, unique: str) -> Callable[[Callable[..., Coroutine]], BasicHandler]:
        def decorator(func: Callable[..., Coroutine]) -> BasicHandler:
            if not inspect.iscoroutinefunction(func):
                raise TypeError(f"传入的函数 {func.__name__} 必须是异步函数")

            # 获取调用者的包的绝对路径
            caller_frame = inspect.stack()[1]
            caller_filename = caller_frame.filename
            script_folder_path = os.path.abspath(
                os.path.dirname(caller_filename))

            def __init__(self):
                super(self.__class__, self).__init__(block=block,
                                                     unique=unique, script_folder_path=script_folder_path)

            # 动态创建处理器类
            DynamicHandler = type(
                func.__name__,
                (handler_class,),
                {
                    '__slots__': tuple(slot for slot in handler_class.__slots__ if slot != '__weakref__'),
                    '__init__': __init__,
                    'handle': cls._create_handle_method(func)
                },
            )

            return DynamicHandler(script_folder_path=script_folder_path)

        return decorator

    @staticmethod
    def _create_handle_method(func: Callable[..., Coroutine]) -> Callable:
        sig = inspect.signature(func)
        param_names = set(sig.parameters.keys())
        has_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

        async def handle(self, bot=None, event=None, msg=None, qq=None, groupid=None, image=None, **kwargs):
            # 创建一个字典来存储匹配的参数
            params = {
                'bot': bot,
                'event': event,
                'msg': msg,
                'qq': qq,
                'groupid': groupid,
                'image': image,
                'self': self,
                'Handler': self,
                **kwargs
            }
            # 保留 func 需要的参数
            matched_params = {k: v for k,
                              v in params.items() if k in param_names}
            # 保留未匹配的参数
            unmatched_params = {k: v for k,
                                v in params.items() if k not in param_names}

            # 构建最终的参数字典
            final_params = matched_params
            if has_kwargs:
                final_params.update(unmatched_params)

            # 调用 func 并传递参数
            await func(**final_params)

        return handle
