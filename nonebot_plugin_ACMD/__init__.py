import time
import asyncio

from nonebot import on_message, logger, get_driver
from nonebot.exception import StopPropagation
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.rule import is_type
from typing import Union

from .cli import App, CommandRegistry
from .ACMD_driver import get_driver as ACMD_get_driver
from .auto_reload import HotSigner, HotPlugin
from .command_signer import BasicHandler
from .already_handler import func_to_Handler
from .command import (
    dispatch as _dispatch,
    CommandFactory,
    Command,
    CommandData
)
from .Atypes import HandlerContext


driver = get_driver()
__version__ = "0.0.2"

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
del ENDC, YELLOW


@driver.on_startup
async def abcstart():
    await ACMD_get_driver().trigger_execution()
    HandlerContext.set_ready()
    HotSigner.set_event_loop(asyncio.get_running_loop())
    HotSigner.start()
    app = App()

    @CommandFactory.CLI_cmd_register('exit_cli')
    async def _():
        app.prompt_manager.stop()
        await app.logger_handler.stop()
        logger.info('已退出CLI')
    app.run()


@total_process.handle()
async def total_stage(bot: Bot, event: Union[GroupMessageEvent, PrivateMessageEvent]):
    msg = event.get_plaintext()

    message_segments = event.get_message()
    image = [seg.data.get('url')
             for seg in message_segments if seg.type == 'image']

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
