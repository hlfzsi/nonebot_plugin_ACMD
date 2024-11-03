from nonebot import on_message, logger
from nonebot.exception import StopPropagation
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.rule import is_type
from typing import Union
import time


from .command import dispatch, CommandFactory, Command, CommandData
from .already_handler import GroupMessageHandler, PrivateMessageHandler, MessageHandler, func_to_Handler
from .command_signer import BasicHandler

rule = is_type(PrivateMessageEvent, GroupMessageEvent)
total_process = on_message(rule=rule, priority=2, block=False)
CommandFactory.create_help_command(owner='origin', help_text='')


@total_process.handle()
async def total_stage(bot: Bot, event: Union[GroupMessageEvent, PrivateMessageEvent]):
    msg = event.get_plaintext()

    image = None
    for seg in event.get_message():
        if seg.type == 'image':
            image = seg.data.get('url')
            break
    try:
        start = time.time()
        await dispatch(message=msg, bot=bot, event=event, image=image)
    except StopPropagation:
        raise
    finally:
        end = time.time()
        logger.info(f"处理消息用时：{end-start}秒")
