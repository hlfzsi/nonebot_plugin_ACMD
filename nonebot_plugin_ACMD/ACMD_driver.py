from __future__ import annotations
import asyncio
from nonebot import logger
from typing import Callable, Tuple, Dict, Any, Set


def get_driver():
    return executor


class FunctionCall:
    __slots__ = ('func', 'args', 'kwargs')

    def __init__(self, func: Callable, args: Tuple = (), kwargs: Dict[str, Any] = None):
        self.func = func
        self.args = args
        self.kwargs = tuple(kwargs.items()) if kwargs else ()

    def __hash__(self) -> int:
        return hash((self.func, self.args, self.kwargs))

    def __eq__(self, other: 'FunctionCall') -> bool:
        return (self.func, self.args, self.kwargs) == (other.func, other.args, other.kwargs)

    def call(self) -> Any:
        result = self.func(*self.args, **dict(self.kwargs))
        return result


class FunctionExecutor:
    __slots__ = ('pending_functions', 'process',
                 'registered_functions', 'on_end_functions')

    def __init__(self):
        self.pending_functions: Set[FunctionCall] = set()
        self.process = False
        self.registered_functions: Dict[Tuple[str, str], FunctionCall] = {}
        self.on_end_functions: Set[FunctionCall] = set()

    def add_call(self, call: FunctionCall, is_on_end=False):
        if is_on_end:
            func_key = (call.func.__module__, call.func.__qualname__)
            if func_key in self.registered_functions:
                old_call = self.registered_functions.pop(func_key)
                self.on_end_functions.discard(old_call)
            self.registered_functions[func_key] = call
            self.on_end_functions.add(call)
        else:
            if not self.process:
                self.pending_functions.add(call)
            else:
                if asyncio.iscoroutinefunction(call.func):
                    asyncio.create_task(call.call())
                else:
                    asyncio.create_task(asyncio.to_thread(call.call))

    async def trigger_execution(self) -> None:
        self.process = True
        tasks = []
        for call in self.pending_functions:
            if asyncio.iscoroutinefunction(call.func):
                task = asyncio.create_task(call.call())
            else:
                task = asyncio.create_task(asyncio.to_thread(call.call))
            tasks.append(task)

        if tasks:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
            for task in done:
                try:
                    await task
                except Exception as e:
                    logger.error(
                        f"An error occurred during execution of a function: {e}")
            self.pending_functions.clear()

    async def trigger_on_end_execution(self) -> None:
        tasks = []
        for call in self.on_end_functions:
            if asyncio.iscoroutinefunction(call.func):
                task = asyncio.create_task(call.call())
            else:
                task = asyncio.create_task(asyncio.to_thread(call.call))
            tasks.append(task)

        if tasks:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
            for task in done:
                try:
                    await task
                except Exception as e:
                    logger.error(
                        f"An error occurred during on_end execution of a function: {e}")
            self.on_end_functions.clear()

    class OnStartDecorator:
        __slots__ = ('executor', 'func')

        def __init__(self, executor: 'FunctionExecutor', func: Callable):
            self.executor = executor
            self.func = func
            self.executor.add_call(FunctionCall(self.func))

        def __call__(self, *args, **kwargs) -> Any:
            call = FunctionCall(self.func, args, kwargs)
            # self.executor.add_call(call)
            return call.call()

    def on_startup(self, func: Callable = None) -> Any:
        if func is None:
            return lambda f: self.OnStartDecorator(self, f)
        return self.OnStartDecorator(self, func)

    class OnEndDecorator:
        __slots__ = ('executor', 'func')

        def __init__(self, executor: 'FunctionExecutor', func: Callable):
            self.executor = executor
            self.func = func
            self.executor.add_call(FunctionCall(self.func), is_on_end=True)

        def __call__(self, *args, **kwargs) -> Any:
            call = FunctionCall(self.func, args, kwargs)
            # self.executor.add_call(call, is_on_end=True)
            return call.call()

    def on_shutdown(self, func: Callable = None) -> Any:
        if func is None:
            return lambda f: self.OnEndDecorator(self, f)
        return self.OnEndDecorator(self, func)


executor = FunctionExecutor()
