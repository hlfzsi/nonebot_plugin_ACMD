from __future__ import annotations
import time
import asyncio

from nonebot import on_message, logger, get_driver
from nonebot.exception import StopPropagation
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.rule import is_type
from nonebot.plugin import PluginMetadata

from .cli import App
from .config import Config
from .ACMD_driver import get_driver as ACMD_get_driver
from .auto_reload import HotSigner
from .command_signer import BasicHandler
from .already_handler import func_to_Handler
from .command import (
    dispatch as _dispatch,
    CommandFactory,
    Command,
    CommandData
)
from .Atypes import HandlerContext, HandlerInvoker
HandlerInvoker.import_BasicHandler()
driver = get_driver()
__version__ = "0.0.4"
__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-ACMD",
    description="插件开发新方案,支持用户输入纠错、命令行指令、热重载，目标是Advanced CMD ( 目前不太可能 )",
    usage="见 https://github.com/hlfzsi/nonebot_plugin_ACMD ",
    type="library",
    homepage="https://github.com/hlfzsi/nonebot_plugin_ACMD",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

ACMD_Processor = on_message(rule=is_type(
    MessageEvent), priority=2, block=False)
CommandFactory.create_help_command(owner='origin', help_text='')


@driver.on_startup
async def abcstart():
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

    @CommandFactory.CLI_cmd_register('Config_ACMD_SimilarityRate')
    async def __(Similarity_Rate: float):
        """临时修改相似度阈值

        Args:
            Similarity_Rate (float): 相似度阈值
        """
        Config.Similarity_Rate = Similarity_Rate
        logger.warning(f'本次运行时相似度阈值被设置为 {Similarity_Rate}')

    app.run()


@ACMD_Processor.handle()
async def total_stage(bot: Bot, event: MessageEvent):
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
