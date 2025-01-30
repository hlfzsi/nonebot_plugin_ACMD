"""
Warning !!!
屎山!
是那种连报错都抛不出来的屎山!
某人摆烂中...
"""
from __future__ import annotations
import asyncio
import threading
import importlib
import importlib.util
import inspect
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from collections import defaultdict

from nonebot import logger
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer
from typing import Dict, Set, List, Optional, Final, Any

from .ACMD_driver import executor
from .command_signer import BasicHandler
from .command import Command
from .cli import CommandRegistry

MAX_RELOAD_WORKERS: Final[int] = 4  # 最大并发重载工作线程数


class DependencyTracker:
    __slots__ = ('dependents_map', 'module_paths', '_lock',
                 '_async_queue', '_async_initialized')

    def __init__(self):
        self.dependents_map: Dict[str, Set[str]] = defaultdict(set)
        self.module_paths: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._async_queue = asyncio.Queue()
        self._async_initialized = False

    async def _async_update_worker(self):
        """异步批量更新工作线程"""
        while True:
            updates = await self._async_queue.get()
            with self._lock:
                for fullname, caller in updates:
                    self._add_dependency(fullname, caller)
            self._async_queue.task_done()

    def _ensure_async_initialized(self):
        """确保异步工作线程初始化"""
        if not self._async_initialized:
            asyncio.get_event_loop().create_task(self._async_update_worker())
            self._async_initialized = True

    def _add_dependency(self, fullname: str, caller: str):
        """原子依赖关系添加"""
        self.dependents_map[fullname].add(caller)
        # 缓存模块路径
        if caller not in self.module_paths:
            if caller in sys.modules:
                module = sys.modules[caller]
                if hasattr(module, '__file__') and module.__file__:
                    self.module_paths[caller] = str(
                        Path(module.__file__).resolve().parent)

    def find_spec(self, fullname: str, path: Optional[List[str]] = None, target: Optional[object] = None):
        # 安全获取调用者帧（降级保护）
        try:
            caller_frame = sys._getframe(5)
        except ValueError:
            caller_frame = sys._getframe(1)

        caller = caller_frame.f_globals.get('__name__', '')

        if not caller or caller == '__main__':
            return None

        if asyncio._get_running_loop():
            self._ensure_async_initialized()
            self._async_queue.put_nowait([(fullname, caller)])
        else:
            with self._lock:
                self._add_dependency(fullname, caller)
        return None

    def _find_dependents(self, package_name: str) -> List[str]:
        """依赖查找"""
        dependents = set()

        # 获取依赖模块
        dependents_modules = self.dependents_map.get(package_name, set())
        for module in dependents_modules:
            if module in self.module_paths:
                dependents.add(self.module_paths[module])

        # 添加自身模块路径
        if package_name in sys.modules:
            module = sys.modules[package_name]
            if hasattr(module, '__file__') and module.__file__:
                path = str(Path(module.__file__).resolve().parent)
                if Path(path).exists():
                    dependents.add(path)

        return list(dependents)


# 注册依赖跟踪器
tracker = DependencyTracker()
sys.meta_path.insert(0, tracker)

# 全局线程池
reload_executor = ThreadPoolExecutor(max_workers=MAX_RELOAD_WORKERS)

# 命令处理器字典
Handler_Dict: Dict[str, List[BasicHandler]] = BasicHandler._path_instances
Command_Dict: Dict[str, List[Command]] = Command._commands_dict


class AsyncReloader(FileSystemEventHandler):
    def __init__(self, package_path: str, loop: asyncio.AbstractEventLoop) -> None:
        self.package_path = package_path
        self.loop = loop
        self.reload_lock = asyncio.Lock()
        self.reload_delay = 1.0
        self.pending_tasks: Set[asyncio.Task] = set()
        self.module_state_cache: Dict[str, Any] = {}
        self._file_event_queue = asyncio.Queue()

    async def process_events(self):
        """任务处理事件队列"""
        while True:
            event = await self._file_event_queue.get()
            async with self.reload_lock:
                await self._schedule_reload(event)
            self._file_event_queue.task_done()

    async def _schedule_reload(self, event: FileSystemEvent):
        """调度重载任务"""
        package_name = self._get_package_name()
        logger.debug(f"Detected change in {
                     package_name}, scheduling reload...")

        # 取消之前的未完成重载任务
        for task in self.pending_tasks:
            if not task.done():
                task.cancel()

        new_task = self.loop.create_task(
            self._debounced_reload(package_name),
            name=f"ReloadTask-{package_name}"
        )
        self.pending_tasks.add(new_task)
        new_task.add_done_callback(lambda t: self.pending_tasks.discard(t))

    async def _debounced_reload(self, package_name: str):
        """防抖重载逻辑"""
        await asyncio.sleep(self.reload_delay)
        await self._safe_reload(package_name)

    async def _safe_reload(self, package_name: str):
        """安全重载包装"""
        try:
            await self._reload_module(package_name)
            logger.success(f"Successfully reloaded package: {package_name}")
        except Exception as e:
            logger.error(f"Reload failed for {package_name}: {str(e)}")

    def on_any_event(self, event: FileSystemEvent) -> None:
        """主线程触发的同步事件处理"""
        if not event.is_directory and event.src_path.endswith('.py'):
            # 将事件推送到异步队列
            self.loop.call_soon_threadsafe(
                self._file_event_queue.put_nowait, event
            )

    def _get_package_name(self) -> str:
        """获取标准化的包名称"""
        return Path(self.package_path).resolve().relative_to(Path.cwd()).as_posix().replace('/', '.')

    async def _reload_module(self, package_name: str) -> None:
        """主重载逻辑"""

        # 清理命令系统
        await self._cleanup_commands(package_name)

        await self.loop.run_in_executor(
            None,
            self._sync_pre_reload,
            package_name
        )

        try:

            # 在线程池执行模块卸载
            await self.loop.run_in_executor(
                reload_executor,
                self._unload_modules,
                package_name
            )

            # 异步加载新模块
            await self._async_load_module(package_name)

        except Exception as e:
            logger.error(f"Reload aborted due to error: {str(e)}")
            raise

    def _sync_pre_reload(self, package_name: str):
        """在主线程执行的预重载操作"""
        # 清理命令注册
        for cmd in CommandRegistry._tracker.get(self.package_path, []):
            CommandRegistry.disable_command(str(cmd))

        # 清理执行器
        for func_key in list(executor.registered_functions.keys()):
            if func_key[0].startswith(package_name):
                task = executor.registered_functions.pop(func_key, None)
                executor.on_end_functions.discard(task)
                if asyncio.iscoroutinefunction(task.func):
                    asyncio.run_coroutine_threadsafe(
                        task.call(), self.loop).result()
                else:
                    asyncio.run_coroutine_threadsafe(
                        asyncio.to_thread(task.call()), self.loop).result()

    def _unload_modules(self, package_name: str):
        """同步卸载模块"""
        modules_to_unload = [
            name for name in sys.modules
            if name == package_name or name.startswith(f"{package_name}.")
        ]
        for name in modules_to_unload:
            del sys.modules[name]

    async def _async_load_module(self, package_name: str) -> Optional[Any]:
        """异步加载模块"""
        init_file = Path(self.package_path) / "__init__.py"
        if not init_file.exists():
            return None

        try:
            spec = importlib.util.spec_from_file_location(
                package_name, init_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Invalid spec for {package_name}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[package_name] = module

            await self.loop.run_in_executor(
                reload_executor,
                spec.loader.exec_module,
                module
            )

            return module
        except SyntaxError as e:
            logger.error(f"Syntax error in {package_name}: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Failed to load {package_name}: {str(e)}")
            raise

    async def _cleanup_commands(self, package_name: str):
        """异步清理命令系统"""
        dependent_modules = await self.loop.run_in_executor(
            None,
            self._find_dependents,
            package_name
        )

        await self._call_command_method('delete', dependent_modules)
        await self.loop.run_in_executor(
            None,
            self._call_handler_method,
            'remove',
            dependent_modules
        )

    def _find_dependents(self, package_name: str) -> List[str]:
        """查找依赖模块"""
        return tracker._find_dependents(package_name)

    async def _call_command_method(self, method: str, modules: List[str]):
        """异步调用命令方法"""
        tasks = []
        for module_path in modules:
            for cmd in Command_Dict.get(module_path, []):
                if method == 'delete':
                    task = cmd.delete(script_folder_path=module_path)
                else:
                    task = getattr(cmd, method)()
                tasks.append(asyncio.create_task(task))
        await asyncio.gather(*tasks, return_exceptions=True)

    def _call_handler_method(self, method: str, modules: List[str]):
        """调用处理器方法"""
        for module_path in modules:
            for handler in Handler_Dict.get(module_path, []):
                getattr(handler, method)()


class HotPlugin:
    def __init__(self) -> None:
        self.observer = Observer()
        self.reloaders: Dict[str, AsyncReloader] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._pending_plugins: List[str] = []

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """绑定到事件循环"""
        self.loop = loop
        # 处理等待中的插件
        for path in self._pending_plugins:
            self._add_reloader(path)
        self._pending_plugins.clear()

    def add_plugin(self) -> None:
        """添加当前调用者的插件"""
        caller_frame = inspect.stack()[1]
        caller_module = inspect.getmodule(caller_frame[0])
        if caller_module is None or not hasattr(caller_module, '__file__'):
            raise RuntimeError("无法确定调用模块路径")

        caller_path = Path(caller_module.__file__).parent
        if not (caller_path / "__init__.py").exists():
            raise ValueError(f"{caller_path} 不是有效的Python包")

        if self.loop is not None and self.loop.is_running():
            self._add_reloader(str(caller_path))
        else:
            self._pending_plugins.append(str(caller_path))

    def _add_reloader(self, package_path: str) -> None:
        """实际添加重载器"""
        if package_path in self.reloaders:
            return

        if self.loop is None:
            raise RuntimeError("事件循环未绑定")

        reloader = AsyncReloader(package_path, self.loop)
        self.reloaders[package_path] = reloader
        self.observer.schedule(reloader, path=package_path, recursive=True)

        # 启动事件处理任务
        self.loop.create_task(reloader.process_events())

    def start(self) -> None:
        """启动热重载系统"""
        if not self._running:
            self.observer.start()
            self._running = True

    async def stop(self) -> None:
        """停止热重载系统"""
        if self._running:
            self.observer.stop()
            await asyncio.to_thread(self.observer.join)
            self._running = False

            # 取消所有进行中的重载任务
            for reloader in self.reloaders.values():
                for task in reloader.pending_tasks:
                    task.cancel()
                await asyncio.gather(*reloader.pending_tasks, return_exceptions=True)


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
