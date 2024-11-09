from functools import wraps
import asyncio

# 尚未实现
class FunctionExecutor:
    def __init__(self, handle_start=False):
        self.handle_start = handle_start
        self.pending_functions = []

    async def set_handle_start(self, value):
        """ 设置 handle_start 的值，并处理待执行的函数。"""
        self.handle_start = value
        if self.handle_start:
            # 执行所有的异步函数
            coroutines = [func(*args, **kwargs) for func, args,
                          kwargs in self.pending_functions if asyncio.iscoroutinefunction(func)]
            await asyncio.gather(*coroutines)
            # 执行所有的同步函数
            for func, args, kwargs in self.pending_functions:
                if not asyncio.iscoroutinefunction(func):
                    func(*args, **kwargs)
            # 清空待处理函数列表
            self.pending_functions.clear()

    def on_startup(self, func):
        """ 装饰器，用于装饰启动时执行的函数。这些函数将在 handle_start 设置为 True 时执行，
        或者如果 handle_start 已经是 True，则立即执行。装饰的函数可以带有参数。"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.handle_start:
                return func(*args, **kwargs)
            else:
                self.pending_functions.append((func, args, kwargs))

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if self.handle_start:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                else:
                    loop.run_until_complete(func(*args, **kwargs))
                    return
                asyncio.run(func(*args, **kwargs))
                return
            else:
                self.pending_functions.append((func, args, kwargs))

        # 返回适当的包装器
        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper


Adriver = FunctionExecutor(handle_start=False)
