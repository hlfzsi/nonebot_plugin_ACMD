import inspect
from functools import update_wrapper, partial
import os
import types

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent

from typing import Callable, Dict, Type, Coroutine, Union, Any, get_type_hints

from abc import abstractmethod

from .command_signer import BasicHandler
from .Atypes import (
    UserInput,
    GroupID,
    ImageInput,
    PIN,
    Record
)


class MessageHandler(BasicHandler):
    __slots__ = tuple(
        slot for slot in BasicHandler.__slots__ if slot != '__weakref__')

    @abstractmethod
    async def handle(self, bot: Bot = None, event: Union[GroupMessageEvent, PrivateMessageEvent] = None, msg: UserInput = None, qq: PIN = None, groupid: GroupID = None, image: ImageInput = None) -> None:
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
    async def handle(self, bot: Bot = None, event: GroupMessageEvent = None, msg: UserInput = None, qq: PIN = None, groupid: GroupID = None, image: ImageInput = None) -> None:
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
    async def handle(self, bot: Bot = None, event: PrivateMessageEvent = None, msg: UserInput = None, qq: PIN = None, groupid: GroupID = None, image: ImageInput = None) -> None:
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
        """创建一个 handle 方法，明确列出所有参数，包括类型注解"""
        sig = inspect.signature(func)
        params = list(sig.parameters.values())

        # 获取函数的类型注解
        type_hints = get_type_hints(func)

        # 构建新的参数列表，将 'self' 添加为第一个参数，除非 'func' 已经有 'self'
        new_params = [inspect.Parameter(
            'self', inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        if not (params and params[0].name == 'self'):
            for param in params:
                annotation = type_hints.get(param.name, param.annotation)
                new_params.append(inspect.Parameter(
                    param.name,
                    param.kind,
                    default=param.default,
                    annotation=annotation
                ))

        # 构建新的签名
        new_sig = sig.replace(parameters=new_params)

        async def handle(self, *args, **kwargs):
            bound_args = new_sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()
            return await func(*bound_args.args[1:], **bound_args.kwargs)

        # 更新 handle 方法的签名以匹配新的参数列表
        handle.__signature__ = new_sig

        wrapper = update_wrapper(handle, func)

        return wrapper
