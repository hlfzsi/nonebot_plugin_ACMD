from nonebot import logger
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent, Bot
from typing import Union
import asyncio

from nonebot_plugin_ACMD import ACMD_get_driver, HotSigner, CommandFactory, func_to_Handler, PrivateMessageHandler, BasicHandler

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
    await bot.send(event, 'Hello,world!')
    # pass or do something...


class MYHandler(PrivateMessageHandler):
    # 这里类型标注省略，实际开发中强烈建议添加类型标注，它可以在BasicHandler中找到示例
    async def handle(self, bot=None, event=None, msg=None, qq=None, groupid=None, image=None, **kwargs):
        # Do something...
        return


# 进行命令和处理器的绑定
my_first_cmd = CommandFactory.create_command(
    ['hello', 'hi'], [test, MYHandler()], owner='test')   # 保留你的cmd对象，它可以被动态修改
asyncio.run(my_first_cmd.delete())  # 撤销我的指令
# 注意，cmd对象的大部分操作需要 await


@driver.on_shutdown
async def end():
    logger.debug('ending...')
    # Do some cleaning...
    await asyncio.sleep(3)
