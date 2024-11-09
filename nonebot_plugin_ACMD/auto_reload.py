import importlib
import importlib.util
import asyncio
import os
import aiofiles
import sys
import inspect
from typing import Dict, Set, List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from nonebot import logger
from .command_signer import BasicHandler
from .command import Command

# 依赖跟踪器


class DependencyTracker(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.imports: Dict[str, Set[str]] = {}

    def find_spec(self, fullname, path, target=None):
        caller = sys._getframe(5).f_globals['__name__']
        if caller != '__main__':
            self.imports.setdefault(fullname, set()).add(caller)
        return None  # 继续使用其他 finder


# 注册依赖跟踪器
tracker = DependencyTracker()
sys.meta_path.insert(0, tracker)

# 命令处理器字典
Handler_Dict: Dict[str, List[BasicHandler]] = BasicHandler._path_instances
Command_Dict: Dict[str, List[Command]] = Command._commands_dict


class AsyncReloader(FileSystemEventHandler):
    def __init__(self, package_path: str, queue: asyncio.Queue, loop) -> None:
        self.package_path = package_path
        self.queue = queue
        self.reloading = False  # 标志是否正在进行重新加载
        self.reload_delay = 0.5  # 重新加载延迟时间（秒）
        self.pending_events: Set[FileSystemEvent] = set()  # 用于去重的集合
        self.current_event: Optional[FileSystemEvent] = None  # 当前正在处理的事件
        self.event_task: Optional[asyncio.Task] = None  # 用于合并事件的任务
        self.loop = loop  # 主线程的事件循环
        # 用于避免短时间多次重载

    async def reload_package(self, event: Optional[FileSystemEvent] = None) -> None:
        if self.reloading:
            logger.debug("Reload already in progress, skipping.")
            return
        self.reloading = True

        package_name = self._get_package_name(self.package_path)
        if package_name in sys.modules:
            try:
                await asyncio.sleep(self.reload_delay)
                await self._reload_module(package_name)
                logger.success(f"Reloaded package: {package_name}")
            except Exception as e:
                logger.error(f"Failed to reload package {package_name}: {e}")
                raise
            finally:
                self.reloading = False
        else:
            logger.info(f"Skipped reloading: {package_name} is not loaded")

    def _get_package_name(self, path: str) -> str:
        relative_path = os.path.relpath(path, os.getcwd()).replace(os.sep, '.')
        return relative_path

    async def _reload_module(self, package_name: str) -> None:
        # 处理依赖
        dependent_modules = self._find_dependents(package_name)
        await self._call_command_method('delete', dependent_modules)
        self._call_handler_method('remove', dependent_modules)

        # 卸载模块
        self._unload_module(package_name)

        # 加载模块
        await self._load_module(package_name, self.package_path)

    def _find_dependents(self, package_name: str) -> List[str]:
        # 获取依赖模块的绝对路径
        dependent_modules = list(tracker.imports.get(package_name, []))

        # 添加被更新的模块本身
        if package_name in sys.modules and hasattr(sys.modules[package_name], '__file__'):
            dependent_modules.append(package_name)

        # 返回所有依赖模块的文件夹目录
        return [os.path.dirname(os.path.abspath(sys.modules[mod].__file__)) for mod in dependent_modules if mod in sys.modules and hasattr(sys.modules[mod], '__file__')]

    async def _call_command_method(self, method: str, modules: List[str]) -> None:
        # 收集所有需要调用的命令，防止迭代过程中字典改变
        commands_to_call = []

        for module in modules:
            for command in Command_Dict.get(module, []):
                if method == 'delete':
                    commands_to_call.append(
                        (command, method, {'script_folder_path': module}))
                else:
                    commands_to_call.append((command, method, {}))

        # 在单独的循环中调用收集到的命令
        for command, method, kwargs in commands_to_call:
            if method == 'delete':
                await getattr(command, method)(**kwargs)
            else:
                await getattr(command, method)()

    def _call_handler_method(self, method: str, modules: List[str]) -> None:
        for module in modules:
            for handler in Handler_Dict.get(module, []):
                getattr(handler, f"{method}")()

    def _unload_module(self, package_name: str) -> None:
            # 创建一个列表，包含所有待卸载模块的名称
        modules_to_unload = [name for name in sys.modules if name ==
                            package_name or name.startswith(package_name + '.')]

        # 遍历列表，从sys.modules中移除这些模块
        for name in modules_to_unload:
            del sys.modules[name]

    async def _load_module(self, package_name: str, package_path: str) -> None:
        init_file = os.path.join(package_path, '__init__.py')
        if not os.path.exists(init_file):
            return

        async with aiofiles.open(init_file, mode='rb') as file:
            content = await file.read()
            content = content.replace(b'\x00', b'')

        # 动态加载模块
        spec = importlib.util.spec_from_file_location(package_name, init_file)
        if spec is None:
            raise ImportError(
                f"Module {package_name} not found at {package_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = module

        try:
            await asyncio.to_thread(spec.loader.exec_module, module)
        except SyntaxError as e:
            logger.error(f"Syntax error while loading module {
                         package_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error while loading module {package_name}: {e}")
            raise

    def on_any_event(self, event: FileSystemEvent) -> None:
        if not event.is_directory and event.src_path.endswith('.py'):
            # 检查是否在同一文件夹内
            if self.current_event and os.path.dirname(event.src_path) == os.path.dirname(self.current_event.src_path):
                return

            # 如果当前有任务在运行，忽略新事件
            if self.reloading:
                return

            # 更新当前事件
            self.current_event = event

            # 取消之前的任务（如果有）
            if self.event_task and not self.event_task.done():
                self.event_task.cancel()

            # 创建新的任务
            self.event_task = asyncio.run_coroutine_threadsafe(
                self._handle_event(event), self.loop)

    async def _handle_event(self, event: FileSystemEvent) -> None:
        try:
            await self.reload_package(event)
        except asyncio.CancelledError:
            logger.debug(f"Event handling for {event.src_path} was cancelled")
        finally:
            # 清理当前事件
            self.current_event = None


class HotPlugin:
    def __init__(self, loop: asyncio.AbstractEventLoop = None) -> None:
        self.loop = loop
        self.observer = Observer()
        self.reloader_map: Dict[str, AsyncReloader] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self.pending_plugins: List[str] = []

    def add_plugin(self) -> None:
        # 获取调用者模块的绝对路径
        caller_frame = inspect.stack()[1]
        caller_module = inspect.getmodule(caller_frame[0])
        if caller_module is None or not hasattr(caller_module, '__file__'):
            raise ValueError("Could not determine the caller's module file.")

        caller_file = caller_module.__file__
        if caller_file is None:
            raise ValueError("Caller's module file is None.")

        package_path = os.path.dirname(caller_file)
        if os.path.isfile(os.path.join(package_path, '__init__.py')):
            self._add_plugin(package_path)
        else:
            raise ValueError(
                f"The path {package_path} is not a valid package.")

    def _add_plugin(self, package_path: str) -> None:
        if package_path not in self.reloader_map:
            if self.loop:
                # 如果有 loop，直接添加插件
                reloader = AsyncReloader(
                    package_path, self.task_queue, self.loop)
                self.reloader_map[package_path] = reloader
                self.observer.schedule(
                    reloader, path=package_path, recursive=True)
            else:
                # 如果没有 loop，将插件路径加入到待处理列表
                self.pending_plugins.append(package_path)

    def start(self) -> None:
        if not self.running:
            self.running = True
            self.observer.start()
            if self.loop and self.loop.is_running():
                self.loop.create_task(self._process_tasks())

    async def _process_tasks(self) -> None:
        while self.running:
            func, args = await self.task_queue.get()
            try:
                if func:
                    await func(*args)
            finally:
                self.task_queue.task_done()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        if self.loop and self.loop.is_running():
            # 处理堆积的插件任务
            for package_path in self.pending_plugins:
                self._add_plugin(package_path)
            self.pending_plugins.clear()

    def stop(self) -> None:
        self.running = False
        self.observer.stop()
        self.observer.join()
        if self.loop and self.loop.is_running():
            self.loop.stop()


HotSigner = HotPlugin()
# 示例
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    plugin = HotPlugin()
    plugin.add_plugin()  # 自动获取调用者的包路径
    plugin.start()
    plugin.set_event_loop(loop)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        plugin.stop()
