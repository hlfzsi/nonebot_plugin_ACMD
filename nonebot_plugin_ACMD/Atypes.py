from dataclasses import dataclass, field
import asyncio
from queue import Queue
from inspect import _empty, signature
import httpx
import aiofiles
from typing import (
    Dict, List, Optional, Union, Tuple, get_origin, get_args, get_type_hints,
    ForwardRef, Any, Awaitable
)
import os

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.exception import StopPropagation


class AsyncFuncFaker:
    __slots__ = ('coro_func')

    def __init__(self, coro_func):
        self.coro_func = coro_func

    def __call__(self, *args, **kwargs):
        return self.coro_func(*args, **kwargs)


@dataclass(slots=True)
class UserInput:
    """
    用于存储用户输入信息的数据类。

    属性:
        body (str): 用户消息去除命令部分的字符串。例如，如果用户发送的消息是“/command message”，则body将是“message”。
        full (str): 完整的用户消息字符串，包含用户发送的所有内容。
        cmd (str): 用户所触发的具体命令
    """
    body: str
    """
    说明: 用户消息去除命令部分。
    示例: 如果用户发送的消息是“/command message”，则body将是“message”。
    """
    full: str
    """
    说明: 完整用户消息，包括所有命令和参数。
    """
    cmd: str
    """
    说明: 用户所触发的具体命令。
    """


@dataclass(slots=True)
class GroupID:
    """
    数据类，用于表示群组的标识符，同时提供字符串和整数两种格式。

    属性:
        str (str): 群号的字符串形式。
        int (int): 群号的整数形式。
    注意: str和int应表示相同的群组。
    """
    str: str
    """
    说明: 群号(str)，表示一个群组的字符串形式标识符。
    """
    int: int
    """
    说明: 群号(int)，表示同一个群组的整数形式标识符。
    注意: 此值应与str属性表示同一群组。
    """


@dataclass(slots=True)
class PIN:
    """
    数据类，用于存储用户的个人信息，包括用户标识符和头像链接。

    属性:
        user (str): 用户的唯一标识符，通常是QQ号，对于官方机器人则是由协议端提供的唯一标识符。
        avatar_url (str): 用户头像的URL链接。
    """
    user: str
    """
    说明: 通常是用户QQ号(str)，对于官bot是由协议端提供的唯一标识符。
    """
    avatar_url: str
    """
    说明: 用户头像链接，指向用户头像的网络地址。
    """


@dataclass(slots=True)
class ImageInput:
    """
    图片输入数据类，用于存储用户提供的图片URL列表，并提供下载功能。
    """
    image_list: List[str]
    """
    说明: 用户输入的图片部分(List[str])。
    """

    async def download(
        self,
        target_image: Optional[Union[List[int], int]] = None,
        return_byte: bool = False,
        target_folder: Optional[str] = '.',
        image_name: Optional[str] = None,
        semaphore_count: int = 3
    ) -> Optional[List[bytes]]:
        """
        下载image_list中指定的图片。

        参数:
        - target_image (Optional[Union[List[int], int]]): 指定要下载的图片索引或索引列表。默认为None，表示下载所有图片。
        - return_byte (bool): 如果为True，则返回下载的图片字节内容；否则保存到本地文件系统。默认为False。
        - target_folder (Optional[str]): 指定保存下载图片的目标文件夹路径。默认为当前目录('.')。
        - image_name (Optional[str]): 指定保存的图片名前缀（如果return_byte为False）。默认为None。
        - semaphore_count (int): 并发下载的最大数量。默认为3。

        返回:
        - Optional[List[bytes]]: 如果return_byte为True，则返回包含下载图片字节内容的列表；否则返回None。
        """
        if not self.image_list:
            return

        if not return_byte:
            os.makedirs(target_folder, exist_ok=True)

        semaphore = asyncio.Semaphore(semaphore_count)
        results = [None] * len(self.image_list)  # 初始化结果列表，大小为image_list的长度

        async with httpx.AsyncClient() as client:
            tasks = [
                self._download_image(
                    client, i, url, target_folder, image_name, semaphore, return_byte)
                for i, url in enumerate(self.image_list)
                if target_image is None or i in ([target_image] if isinstance(target_image, int) else target_image)
            ]
            for task in asyncio.as_completed(tasks):
                index, result = await task
                if return_byte and result is not None:
                    results[index] = result

        filtered_results = [result for result in results if result is not None]
        return filtered_results if return_byte else None

    async def _download_image(
        self,
        client: httpx.AsyncClient,
        index: int,
        url: str,
        target_folder: str,
        image_name: Optional[str],
        semaphore: asyncio.Semaphore,
        return_byte: bool
    ) -> Tuple[int, Optional[bytes]]:
        """
        内部方法，用于实际执行下载操作。

        参数:
        - client (httpx.AsyncClient): 异步HTTP客户端。
        - index (int): 当前处理的图片在image_list中的索引。
        - url (str): 要下载的图片URL。
        - target_folder (str): 目标文件夹路径。
        - image_name (Optional[str]): 图片名称前缀。
        - semaphore (asyncio.Semaphore): 并发控制信号量。
        - return_byte (bool): 是否返回字节内容。

        返回:
        - Tuple[int, Optional[bytes]]: 包含图片索引和下载结果（如果是return_byte为True，则为字节内容；否则为None）的元组。
        """
        async with semaphore:
            try:
                response = await client.get(url)
                response.raise_for_status()

                if return_byte:
                    return index, response.content
                else:
                    file_extension = os.path.splitext(url)[1]
                    base_filename = f"{image_name}_{
                        index}" if image_name else f"{hash(url)}"
                    filename = os.path.join(
                        target_folder, f"{base_filename}{file_extension}")

                    async with aiofiles.open(filename, mode='wb') as file:
                        await file.write(response.content)
                    return index, None
            except Exception as e:
                logger.error(f"下载 {url} 失败: {e}", exc_info=True)
                return index, None


@dataclass(order=True)
class Record:
    """消息处理记录"""
    similarity: float = field(default=100.0, compare=True)
    handlers: List[int] = field(default_factory=list, compare=False)
    futures: Dict[int, asyncio.Task[Any]] = field(
        default_factory=dict, compare=False)

    @staticmethod
    def colored(text: str, color_code: int) -> str:
        """用给定的颜色代码包装文本"""
        return f"\033[{color_code}m{text}\033[0m"

    def __str__(self) -> str:
        # 定义颜色代码
        color_similarity = 36  # 青色
        color_handlers = 35    # 紫色
        color_futures = 32     # 绿色
        color_misc = 90        # 深灰色（用于其它信息）

        # 构建属性字符串表示
        attr_str_parts = []
        for key in ['similarity', 'handlers', 'futures']:
            value = getattr(self, key)
            if key == "similarity":
                color = color_similarity
            elif key == "handlers":
                color = color_handlers
            else:  # key == "futures"
                color = color_futures

            # 特殊处理futures属性
            if key == "futures":
                value_str = "{  " + ", ".join(f"{k}: {v._state}" for k,
                                              v in value.items()) + "  }" if value else "{}"
            else:
                value_str = str(value)

            attr_str_parts.append(f"{self.colored(key, color_misc)}  =  {
                                  self.colored(value_str, color)}")

        attr_str = "\n".join(attr_str_parts)
        return f"{self.colored(self.__class__.__name__, color_misc)}({attr_str})"


class HandlerContext:
    msg: UserInput
    image: ImageInput
    pin: PIN
    groupid: GroupID
    bot: Bot
    event: MessageEvent
    record: Record

    @staticmethod
    def colored(text: str, color_code: int) -> str:
        """用给定的颜色代码包装文本"""
        return f"\033[{color_code}m{text}\033[0m"

    def __str__(self) -> str:
        # 定义颜色代码
        colors = {
            "msg": 36,    # 青色
            "image": 35,  # 紫色
            "pin": 31,    # 红色
            "groupid": 34,  # 蓝色
            "event": 33,  # 黄色
            "_task_queue_size": 90,  # 深灰色
            "_ready": 90,  # 深灰色
        }

        attr_str_parts = []
        for key, value in vars(self).items():
            if key in ["bot", "record"]:  # 对于这些字段，我们不应用颜色
                attr_str_parts.append(
                    f"{self.colored(key, 90)}  =  {str(value)}")
            elif key in colors:
                colored_key = self.colored(key, 90)
                colored_value = self.colored(str(value), colors[key])
                attr_str_parts.append(f"{colored_key}={colored_value}")
            else:
                # 动态处理未知字段，这里默认不染色
                attr_str_parts.append(
                    f"{self.colored(key, 90)}  =  {str(value)}")

        # 添加特殊属性
        attr_str_parts.append(f"{self.colored('_task_queue_size', 90)}  =  {
                              self.colored(str(self._task_queue.qsize()), 90)}")
        attr_str_parts.append(f"{self.colored('_ready', 90)}  =  {self.colored(
            'set' if self._ready.is_set() else 'not set', 90)}")

        attr_str = " , ".join(attr_str_parts)
        return f"{self.colored(self.__class__.__name__, 90)}({attr_str})"

    def __init__(self, msg: UserInput, image: ImageInput, pin: PIN, groupid: GroupID, bot: Bot, event: MessageEvent, record: Record):
        self.msg = msg
        self.image = image
        self.pin = pin
        self.groupid = groupid
        self.bot = bot
        self.event = event
        self.record = record

    _type_cache: Dict = {}
    _ready: asyncio.Event = asyncio.Event()
    _task_queue: Queue = Queue()

    @classmethod
    def _resolve_forward_ref(cls, forward_ref: ForwardRef, globalns: Dict[str, Any], localns: Dict[str, Any]) -> type:
        """解析前向引用到实际类型"""
        return forward_ref._evaluate(globalns, localns)

    @classmethod
    def _normalize_type(cls, param_type: Any, globalns: Dict[str, Any], localns: Dict[str, Any]) -> Union[type, Tuple[type, ...]]:
        """
        将参数类型标准化为单个类型或类型元组。
        处理嵌套的泛型类型，包括但不限于 Union 和 Optional。
        使用缓存来避免重复计算。
        """
        if isinstance(param_type, ForwardRef):
            param_type = cls._resolve_forward_ref(
                param_type, globalns, localns)

        cache_key = (param_type, id(globalns), id(localns))
        if cache_key in cls._type_cache:
            return cls._type_cache[cache_key]

        origin = get_origin(param_type)
        if origin is None:  # 如果不是泛型，则直接返回类型本身
            result = param_type or Any
        elif origin in (Union, Optional):
            types = tuple(cls._normalize_type(arg, globalns, localns)
                          for arg in get_args(param_type) if arg is not type(None))
            result = types if len(types) > 1 else types[0] if types else Any
        else:
            # 对于其他泛型类型（如 List, Dict 等），递归处理其参数
            args = tuple(cls._normalize_type(arg, globalns, localns)
                         for arg in get_args(param_type))
            result = param_type if not args else param_type[args]

        cls._type_cache[cache_key] = result
        return result

    @classmethod
    def fill_parameters(cls, handler: 'BasicHandler') -> Tuple[Tuple[str, ...], ...]:
        """
        根据处理器的方法签名映射参数到HandlerContext字段。

        参数:
            handler (BasicHandler): 要填充参数的处理器实例。

        返回:
            Tuple[Tuple[str, ...], ...]: 每个方法对应的HandlerContext字段名组成的元组列表。
        """
        field_by_type = {
            cls._normalize_type(field_type, globals(), locals()): field_name
            for field_name, field_type in cls.__annotations__.items() if not field_name.startswith('_')
        }

        def map_parameter(normalized_type: Union[type, Tuple[type, ...]]) -> str:
            """根据规范化后的类型映射到HandlerContext字段名称"""
            if isinstance(normalized_type, tuple):
                for t in normalized_type:
                    if (field_name := field_by_type.get(t)) is not None:
                        return field_name
                    if any(issubclass(t, field_type) for field_type in field_by_type):
                        return next(field_name for field_type, field_name in field_by_type.items() if issubclass(t, field_type))
            else:
                if (field_name := field_by_type.get(normalized_type)) is not None:
                    return field_name
                if any(issubclass(normalized_type, field_type) for field_type in field_by_type):
                    return next(field_name for field_type, field_name in field_by_type.items() if issubclass(normalized_type, field_type))

            raise RuntimeError(
                f'{handler} 的 {func_name} 无法映射参数类型 {normalized_type} 到 HandlerContext 字段')

        result = []
        for func_name in ('should_handle', 'handle', 'should_block'):
            func = getattr(handler, func_name, None)
            if not func:
                raise RuntimeError(f'{handler} 不合法, 缺少 {func_name} 方法')

            # 获取全局和局部命名空间字典
            globalns = globals()
            localns = func.__globals__ if hasattr(func, '__globals__') else {}

            # 获取方法的类型提示
            type_hints = get_type_hints(
                func, globalns=globalns, localns=localns)

            sig = signature(func)
            mapped_fields = []
            for name, param in sig.parameters.items():
                if param.annotation is _empty and name not in type_hints:
                    raise RuntimeError(
                        f'{handler} 的方法 {func_name} 的参数 {name} 缺少类型注解')

                normalized_type = cls._normalize_type(
                    type_hints.get(name, param.annotation), globalns, localns)
                mapped_fields.append(map_parameter(normalized_type))

            result.append(tuple(mapped_fields))

        return tuple(result)

    @classmethod
    def insert_field(cls, field: str, field_type: type, func: Awaitable):
        """
        动态地向HandlerContext类中插入一个新的字段,并设置默认值。

        参数:
            field (str): 新字段的名称。
            field_type (type): 新字段的类型。
            func (Awaitable): 新字段的异步加载器。
        """
        cls.__annotations__[field] = field_type
        setattr(cls, field, AsyncFuncFaker(func))

    @classmethod
    def analyse_parameters(cls, handler: 'BasicHandler') -> Union[Tuple[Tuple[str, ...], ...], str]:
        """
        分析给定处理器的参数，如果未准备好则将任务加入队列。
        """
        if cls._ready.is_set():
            return cls.fill_parameters(handler)
        else:
            cls._task_queue.put(handler)
            return 'Waiting'

    @classmethod
    def set_ready(cls) -> None:
        """
        尝试执行队列中的任务。
        """
        cls._ready.set()
        while not cls._task_queue.empty():
            handler: 'BasicHandler' = cls._task_queue.get()
            handler.parameters = cls.fill_parameters(handler)


class HandlerInvoker:
    @staticmethod
    def import_BasicHandler():
        """无奈ing"""
        global BasicHandler
        from .command_signer import BasicHandler

    @classmethod
    async def invoke_handler(
        cls,
        handler_id: int,
        context: 'HandlerContext',
        rasie_StopPropagation: bool = True
    ) -> None:
        handler = BasicHandler.get_handler_by_id(handler_id)
        if not handler:
            return

        for func_name in ('should_handle', 'handle', 'should_block'):
            func = getattr(handler, func_name, None)
            if not func:
                continue

            # 获取当前函数需要的参数名称列表
            param_names = handler.parameters[(
                'should_handle', 'handle', 'should_block').index(func_name)]

            # 动态获取参数值，并识别异步函数
            results = [(var, getattr(context, var), isinstance(getattr(context, var, None), AsyncFuncFaker))
                       for var in param_names]

            # 初始化params，保持参数位置不变
            params = [None] * len(param_names)
            generators = []

            for idx, (var, val, is_coro) in enumerate(results):
                if is_coro:
                    generators.append((idx, var, val(context)))  # 存储索引以保持位置
                else:
                    params[idx] = val  # 直接设置非协程参数

            # 如果有异步函数，等待它们完成并更新context和params
            if generators:
                results = await asyncio.gather(*(gen for _, _, gen in generators))
                for (idx, var_name, _), result in zip(generators, results):
                    setattr(context, var_name, result)
                    params[idx] = result  # 根据索引更新params中的值

            # 执行当前函数
            match func_name:
                case 'should_handle':
                    if not await func(*params):
                        return

                case 'handle':
                    task = asyncio.create_task(func(*params))
                    context.record.futures[handler_id] = task

                case 'should_block':
                    if await func(*params) and rasie_StopPropagation is True:
                        raise StopPropagation

                case _:
                    pass
