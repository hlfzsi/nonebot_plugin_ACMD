from nonebot import logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent, Bot
from typing import Union
import asyncio

from nonebot_plugin_ACMD import ACMD_get_driver, HotSigner, CommandFactory, func_to_Handler, BasicHandler
from nonebot_plugin_ACMD.Atypes import Bot, MessageEvent, Record, HandlerContext


driver = ACMD_get_driver()
HotSigner.add_plugin()  # 添加热重载支持


@driver.on_startup
async def greet():
    # 为其他处理器添加依赖许可。在ACMD的driver内进行依赖注入是安全的，这也是推荐做法。
    @CommandFactory.parameter_injection(field="my_injection", field_type=str)
    async def injection(context: HandlerContext):  # 所有依赖注入器应当接受且仅接受HandlerContext传入
        return f"{context.pin.user}{context.groupid.str}"
    # my_injection将会对应这个函数

    logger.info('Hello,world!')
    # Do something...


# 通过装饰器构建处理器
@func_to_Handler.all_message_handler(block=True)
# 依赖类型进行注入
async def test(bot: Bot, event: Union[GroupMessageEvent, PrivateMessageEvent]):
    await bot.send(event, 'Hello,world!')
    # pass or do something...


class MYHandler(BasicHandler):
    # 实际开发中必须添加类型标注，它可以在BasicHandler中找到示例
    # 这里 PIN 由于我们的依赖注入，应该是f"{context.pin.user}{context.groupid.str}"
    async def handle(self, bot: Bot, event: MessageEvent, record: Record, PIN: str):
        # Do something...
        await bot.send(event, f'你好{PIN}\n本指令相似度为 {record.similarity}')
        return


# 进行命令和处理器的绑定
my_first_cmd = CommandFactory.create_command(
    # 保留你的cmd对象，它可以被动态修改
    ['hello', 'hi', 'world', '/love', '/test', '/this is a demo', '234234234', '222', 'hhh'], [MYHandler(block=False), test], owner='test')
"""
这个命令的输出应当是：
    - 相似度为 something
    - Hello,world!
"""


# 无条件触发的处理器  对于此类处理器，block会自动失效，即使被显式设置为True
# 若必须触发阻断，请手动raise   （不推荐的做法！因为无条件触发的处理器不会保留顺序）
Unconditional_cmd = CommandFactory.create_command(
    commands=None, handler_list=test)
"""
这个命令的输出应当是：
    - Hello,world!
"""


@driver.on_shutdown
async def end():
    logger.debug('ending...')
    # Do some cleaning...
    await asyncio.sleep(1)
