from nonebot import on_message, logger,get_driver
from nonebot.exception import StopPropagation
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.rule import is_type
from typing import Union
import time
import asyncio
driver = get_driver()
__version__="0.0.1"

from .command import CommandFactory, Command, CommandData
from .command import dispatch as _dispatch
from .already_handler import func_to_Handler
from .command_signer import BasicHandler
from .auto_reload import HotSigner, HotPlugin
from .ACMD_driver import get_driver as ACMD_get_driver
from .similarity import similarity as _similarity
rule = is_type(PrivateMessageEvent, GroupMessageEvent)
total_process = on_message(rule=rule, priority=2, block=False)
CommandFactory.create_help_command(owner='origin', help_text='')
YELLOW = '\033[93m'
ENDC = '\033[0m'
print(rf"""{YELLOW}
                       _   _                       _____ __  __ _____
     /\               | | | |                     / ____|  \/  |  __ \
    /  \   _ __   ___ | |_| |__   ___ _ __       | |    | \  / | |  | |
   / /\ \ | '_ \ / _ \| __| '_ \ / _ | '__|      | |    | |\/| | |  | |
  / ____ \| | | | (_) | |_| | | |  __| |         | |____| |  | | |__| |
 /_/    \_|_| |_|\___/ \__|_| |_|\___|_|          \_____|_|  |_|_____/

{ENDC}""")
logger.info("ACMD is initializing... please wait")
_similarity("hello","world")
del ENDC,YELLOW

@driver.on_startup
async def abcstart():
    await ACMD_get_driver().trigger_execution()
    HotSigner.set_event_loop(asyncio.get_running_loop())
    HotSigner.start()


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
        await _dispatch(message=msg, bot=bot, event=event, image=image)
    except StopPropagation:
        raise
    finally:
        end = time.time()
        logger.info(f"处理消息用时：{end-start}秒")

@driver.on_shutdown
async def shut_up():
    await ACMD_get_driver().trigger_on_end_execution()