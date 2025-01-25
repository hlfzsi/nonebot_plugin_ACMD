from nonebot import logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent, Bot
from typing import Union
import asyncio

from nonebot_plugin_ACMD import ACMD_get_driver, HotSigner, CommandFactory, func_to_Handler, BasicHandler
from nonebot_plugin_ACMD.Atypes import Bot,MessageEvent,Record


driver = ACMD_get_driver()
HotSigner.add_plugin()  # 添加热重载支持


@driver.on_startup
async def greet():
    logger.info('Hello,world!')
    # Do something...
    print("greet is decorated and called")


# 通过装饰器构建处理器
@func_to_Handler.all_message_handler()
# 通过变量名进行注入
async def test(bot: Bot, event: Union[GroupMessageEvent, PrivateMessageEvent]):
    await bot.send(event, f'Hello,world!')
    # pass or do something...


class MYHandler(BasicHandler):
    # 实际开发中必须添加类型标注，它可以在BasicHandler中找到示例
    async def handle(self, bot:Bot, event:MessageEvent,record:Record):
        # Do something...
        si=record.similarity
        await bot.send(event, f'Hello,world!\n相似度为 {si}')
        return


# 进行命令和处理器的绑定
my_first_cmd = CommandFactory.create_command(
    # 保留你的cmd对象，它可以被动态修改
    ['hello', 'hi', 'world', '/love', '/test', '/this is a demo','234234234','222','hhh'], [test,MYHandler(block=True)], owner='test')


@driver.on_shutdown
async def end():
    logger.debug('ending...')
    # Do some cleaning...
    await asyncio.sleep(1)
