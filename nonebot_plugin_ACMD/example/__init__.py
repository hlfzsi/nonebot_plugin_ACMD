from nonebot import on_message, logger,get_driver
from nonebot.exception import StopPropagation
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.rule import is_type
from typing import Union
import time
import os

from nonebot_plugin_ACMD import Adriver,HotSigner,CommandFactory,func_to_Handler,PrivateMessageHandler

rule = is_type(PrivateMessageEvent, GroupMessageEvent)

HotSigner.add_plugin()

@Adriver.on_startup
async def abc2start():
    logger.info('hellonhello')
    print("abc2start is decorated and called")
abc2start()


@func_to_Handler.all_message_handler()
async def tester(bot,event):
    await bot.send(event,'Hello,world! again')
a=CommandFactory.create_command(['hello','hi'],[tester],owner='test')

class cascwf(PrivateMessageHandler):
    async def handle(self, bot=None, event=None, msg=None, qq=None, groupid=None, image=None, **kwargs):
        return 
    
b=cascwf()