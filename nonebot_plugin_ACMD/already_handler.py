from abc import abstractmethod
from typing import Union, Optional, Any, Callable, Type, Coroutine
import inspect
from .command_signer import BasicHandler


class MessageHandler(BasicHandler):
    __slots__ = BasicHandler.__slots__

    @abstractmethod
    async def handle(self, bot=None, event=None, msg=None, qq=None, groupid=None, image=None, **kwargs):
        pass


class GroupMessageHandler(BasicHandler):
    __slots__ = BasicHandler.__slots__

    @abstractmethod
    async def handle(self, bot=None, event=None, msg=None, qq=None, groupid=None, image=None, **kwargs):
        pass

    async def should_handle(self, **kwargs):
        if 'event' in kwargs:
            return not self.is_PrivateMessageEvent(kwargs['event'])
        else:
            raise ValueError("Missing event")


class PrivateMessageHandler(BasicHandler):
    __slots__ = BasicHandler.__slots__

    @abstractmethod
    async def handle(self, bot=None, event=None, msg=None, qq=None, groupid=None, image=None, **kwargs):
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

        :param handler_class: 处理器类，如 MessageHandler, GroupMessageHandler, PrivateMessageHandler
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
            DynamicHandler = type(
                func.__name__,
                (handler_class,),
                {
                    '__slots__': handler_class.__slots__,
                    '__init__': lambda self: handler_class.__init__(self, block=block, unique=unique),
                    'handle': cls._create_handle_method(func)
                }
            )
            return DynamicHandler()
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
