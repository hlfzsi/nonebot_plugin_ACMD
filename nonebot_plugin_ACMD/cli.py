import asyncio
import inspect
import sys
import os
from functools import wraps
from inspect import signature, Parameter, getdoc
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Type, get_type_hints

from prompt_toolkit import ANSI, PromptSession, print_formatted_text
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout
from nonebot import logger
from nonebot.log import default_filter, default_format


class CommandRegistry:
    commands: Dict[str, Callable[..., Awaitable[None]]] = {}
    param_hints: Dict[str, Dict[str, Any]] = {}
    prompt_managers: List['PromptManager'] = []
    _tracker : Dict[str, List[str]] = {}

    @classmethod
    def register(cls, cmd: str):
        # 获取调用者的包的绝对路径
        caller_frame = inspect.stack()[1]
        caller_filename = caller_frame.filename
        script_folder_path = os.path.abspath(
            os.path.dirname(caller_filename))

        def decorator(func: Callable[..., Awaitable[None]]):
            sig = signature(func)
            hints = get_type_hints(func)
            func_doc = getdoc(func) or ''

            params = []
            for param_name, param in sig.parameters.items():
                if param_name == 'self' or param_name == 'cls':  # 忽略类方法的第一个参数
                    continue
                param_info = {
                    'name': param_name,
                    'type': hints.get(param_name, Any),
                    'default': param.default if param.default != Parameter.empty else None,
                    'required': param.default == Parameter.empty,
                }
                params.append(param_info)

            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> None:
                await func(*args, **kwargs)

            # 根据原始函数的类型选择合适的包装方式
            if isinstance(func, classmethod):
                wrapped_func = classmethod(wrapper)
            elif isinstance(func, staticmethod):
                wrapped_func = staticmethod(wrapper)
            else:
                wrapped_func = wrapper

            cls.commands[cmd] = wrapped_func
            cls.param_hints[cmd] = {'params': params, 'doc': func_doc}
            cls.update_completers()
            if script_folder_path not in cls._tracker:
                cls._tracker[script_folder_path] = []
            cls._tracker[script_folder_path].append(cmd)

            # 返回适当的包装函数
            return wrapped_func if isinstance(func, (classmethod, staticmethod)) else wrapper

        return decorator

    @staticmethod
    async def _noop_async_function(*args, **kwargs):
        """占位符异步函数，用于替换被禁用的命令"""
        logger.warning('该命令被暂时禁用')

    @classmethod
    def disable_command(cls, name: str):
        """
        禁用指定名称命令，通过将其替换为一个不执行任何操作的异步函数来实现。
        """
        if name in cls.commands:
            cls.commands[name] = cls._noop_async_function

    @classmethod
    def get_command(cls, name: str) -> Callable[..., Awaitable[None]]:
        return cls.commands.get(name)

    @classmethod
    def update_completers(cls):
        for manager in cls.prompt_managers:
            manager.update_completer()

    @classmethod
    def get_param_hints(cls, name: str) -> List[str]:
        return cls.param_hints.get(name, {}).get('params', {})


class LoggerHandler:
    def __init__(self):
        self.log_queue: asyncio.Queue[str] = asyncio.Queue()
        logger.remove()
        logger.add(self.enqueue_log, format=default_format, level=0, filter=default_filter, colorize=True,
                   backtrace=True, diagnose=True, enqueue=True)
        self._print_task = asyncio.create_task(self.print_logs())

    def enqueue_log(self, message):
        if not isinstance(message, str):
            message = str(message)
        self.log_queue.put_nowait(message)

    async def print_logs(self) -> None:
        while True:
            message = await self.log_queue.get()
            with patch_stdout():
                print_formatted_text(ANSI(message), end='')
            self.log_queue.task_done()

    async def stop(self):
        # 停止打印日志的任务
        self._print_task.cancel()
        try:
            await self._print_task
        except asyncio.CancelledError:
            pass

        logger.remove()
        logger.add(sys.stdout, format=default_format, level=0,
                   filter=default_filter, diagnose=False)


class PromptManager:
    def __init__(self, command_registry: CommandRegistry):
        self.session = PromptSession('>', reserve_space_for_menu=8)
        self.command_registry = command_registry
        self.completer = WordCompleter(
            command_registry.commands.keys(), ignore_case=True, sentence=True)
        self.session.completer = self.completer
        command_registry.prompt_managers.append(self)
        self._stop_event = asyncio.Event()

    def update_completer(self):
        self.completer.words = list(self.command_registry.commands.keys())

    async def parse_input(self) -> None:
        while not self._stop_event.is_set():
            try:
                with patch_stdout():
                    user_input: str = await self.session.prompt_async()

                if not user_input.strip():
                    continue

                command_name, args, expected_params = self.find_command_with_args(
                    user_input)
                if command_name is not None:
                    command = self.command_registry.get_command(command_name)
                    if command:
                        try:
                            prepared_args = self.prepare_args(
                                args, expected_params)
                            await command(*prepared_args)
                        except (EOFError, KeyboardInterrupt):
                            logger.warning("请使用 exit_cli 指令退出交互模式")
                        except Exception as e:
                            logger.critical(f'执行命令 {command_name} 时出现错误 {e}')
                            self.print_usage(command_name)
                            logger.warning(f'先前命令输入 : {user_input}')
                    else:
                        logger.error(f"未知命令: {command_name}")
                else:
                    logger.error("无法解析命令")
            except (EOFError, KeyboardInterrupt):
                self.stop()
                logger.warning("建议使用 exit_cli 指令退出交互模式")
                logger.warning("请再次按下 CTRL+C 来完成退出")

    def find_command_with_args(self, user_input: str) -> Tuple[Optional[str], List[str], List[Dict]]:
        commands = self.command_registry.commands.keys()
        parts = user_input.split()  # 按照空格分割输入
        potential_command = ''

        for i in range(len(parts)):
            # 构建潜在命令，依次增加部分，直到匹配到命令或者用尽所有部分
            potential_command += ('' if not potential_command else ' ') + \
                parts[i]
            if potential_command in commands:
                break
        else:
            # 如果没有从循环中break，说明没有找到匹配的命令。
            return None, [], []

        # 命令后的其余部分被认为是参数。
        remaining_parts = parts[i+1:] if i < len(parts) - 1 else []
        args = remaining_parts

        expected_params = self.command_registry.get_param_hints(
            potential_command)
        return potential_command, args, expected_params or []

    def prepare_args(self, args: List[str], expected_params: List[Dict]) -> List[Any]:
        prepared_args = []
        arg_iter = iter(args)

        for param_info in expected_params:
            if param_info['required']:
                try:
                    arg_value = next(arg_iter)
                    prepared_args.append(self.convert_type(
                        arg_value, param_info['type']))
                except StopIteration:
                    logger.error(f"缺少必需参数: {param_info['name']}")
                    break
            elif 'default' in param_info:
                try:
                    arg_value = next(arg_iter)
                    prepared_args.append(self.convert_type(
                        arg_value, param_info['type']))
                except StopIteration:
                    prepared_args.append(param_info['default'])

        prepared_args.extend(arg_iter)

        return prepared_args

    def convert_type(self, value: str, type_hint: Type[Any]) -> Any:
        try:
            if isinstance(type_hint, type):
                return type_hint(value)
            return value
        except ValueError as e:
            logger.error(f"参数转换失败: {value} 无法转换为 {type_hint}: {e}")
            return value

    def print_usage(self, command_name: str):
        params_info = self.command_registry.param_hints.get(command_name)
        if not params_info or not params_info['params']:
            logger.warning(f"命令 {command_name} 无需参数")
            return

        # 构建简短格式的使用方法字符串
        usage_line = [f"使用方法: {command_name}"]
        for param in params_info['params']:
            arg_str = f"<{param['name']}>" if param['required'] else f"[<{
                param['name']}> default to {param['default']}]"
            usage_line.append(arg_str)

        logger.warning(f"{' '.join(usage_line)}\n{params_info.get(
            'doc')}" if params_info.get('doc') else f"{' '.join(usage_line)}\n该指令提供者没有提供任何文档,猜猜这个函数是干什么的,以及它的参数都是什么东西吧")

    def stop(self) -> None:
        self._stop_event.set()


class App:
    __slots__ = ('command_registry', 'logger_handler', 'prompt_manager')

    def __init__(self):
        self.command_registry = CommandRegistry()
        self.logger_handler = LoggerHandler()
        self.prompt_manager = PromptManager(self.command_registry)

    def run(self):
        try:
            asyncio.create_task(self.prompt_manager.parse_input())
        except KeyboardInterrupt:
            raise

    @staticmethod
    @CommandRegistry.register('Ciallo～(∠・ω< )⌒☆')
    async def Ciallo() -> None:
        logger.success("Ciallo～(∠・ω< )⌒☆")

    @staticmethod
    async def test():
        app = App()
        app.run()
        await asyncio.sleep(90)


if __name__ == "__main__":
    asyncio.run(App.test())
