# nonebot_plugin_ACMD

## 项目简介

本项目旨在为基于 NoneBot 框架提供一套拓展命令系统。<br>

******为什么选择本项目？******<br>

1. 相似度命令匹配：旨在重定向用户错误指令
2. 灵活的命令与处理器：在插件运行过程中，可以随意更改指令文本与其处理器
3. 帮助文档自动生成：免去写 `help`的烦恼，当然，你可以接管 `ACMD`的帮助文档
4. 插件热重载：如果你的插件与 `nonebot`耦合度较低，`ACMD`提供了方便的热重载方法，仅需一行代码

## 性能比较

以 `nonebot`和 `alconna`作比较（斗胆比较，如有错误请指正)<br>

[alconna](https://github.com/nonebot/plugin-alconna)：强大的 Nonebot2 命令匹配拓展，支持富文本/多媒体解析，跨平台消息收发。知名老牌命令拓展。

|                        功能                        | 原生nonebot | alconna              |               ACMD               |
| :------------------------------------------------: | :---------: | -------------------- | :------------------------------: |
|                      补全会话                      |     ✓     | ✓                   | 仅支持 `nonebot-plugin-waiter` |
|                       跨平台                       |     ✗     | ✓                   |                ✗                |
|                        i18n                        |     ✗     | ✓                   |                ✗                |
|                    收发消息支持                    |     ✓     | 绝大多数             |                ✓                |
|                      内置插件                      |  `echo`  | `echo，help，lang` |            `helper`            |
|                    帮助文档生成                    |     ✗     | ✓                   |                ✓                |
|                      指令纠正                      |     ✗     | ✗                   |                ✓                |
|                     插件热重载                     |     ✗     | ✗                   |        部分插件可完全支持        |
|                      动态指令                      |     ✗     | ✗                   |                ✓                |
| 与 `nonebot`相似度<br>（相似度越高学习成本越低） |   `\\`   | 高                   |                中                |
|                      开发方式                      |   装饰器   | 装饰器               |           类 或 装饰器           |

## 安装依赖

安装项目所需的所有依赖项，可以通过运行以下命令完成：<br>

```
pip install pandas
pip install aiosqlite
pip install aiofiles
pip install watchdog
```

## 快速开始

**注意**：不要二次调用 `dispatch` 函数，本插件已经完成了它的调用。<br>
本 README 仅提供大致介绍，详细调用见代码注释。<br>

## 自带命令

- `/help` 由 ACMD 自动生成帮助文档/由接管者提供文档<br>
- 完整指令：`/help [owner] [page]`<br>

## 创建命令

要创建一个新的命令，你可以使用 `CommandFactory.create_command` 方法：<br>

```python
from nonebot_plugin_ACMD import CommandFactory

# 创建一个简单的命令
myCommand = CommandFactory.create_command(
    commands=['/start'], 
    handler_list=[MyStartHandler()],
    owner='my_plugin',
    description='启动机器人',
    full_match=True
)

# CommandFactory.create_command方法会返回一个Command对象，你应当将其作为全局变量维护
```

## 定义处理器

处理器需要继承自 `BasicHandler` 并实现 `handle` 方法。例如：<br>

```python
from nonebot_plugin_ACMD import BasicHandler , func_to_Handler

class MyStartHandler(BasicHandler):
     __slots__ = tuple(slot for slot in BasicHandler.__slots__ if slot != '__weakref__')

    async def handle(self, bot: Bot = None, event: Union[GroupMessageEvent, PrivateMessageEvent] = None, msg: str = None, qq: str = None, groupid: str = None, image: Optional[str] = None, ** kwargs: Any) -> None:
        """处理接收到的消息。

        参数:
            bot (Bot): 机器人实例
            event (Union[GroupMessageEvent, PrivateMessageEvent]): 消息事件
            msg (str): 处理后的消息文本
            qq (str): 发送者的QQ号
            groupid (str): 群组ID（私聊时为 -1 ）
            image (Optional[str]): 图片URL（如果有,且最多一张）
            **kwargs (BasicHandler): 其他关键字参数
        """
        await bot.send(event, "Hello , world!")

@func_to_Handler.all_message_handler()
async def MyStartHandler(bot: Bot,event :Union[GroupMessageEvent, PrivateMessageEvent]):
    await bot.send(event,'Hello , world!')

# 以上两种写法等效。对于装饰器写法，函数的传入变量基于变量名称注入，而非类型；额外地，它还拥有等价的 Handler 和 self 传入变量，它们相当于类写法中的 self

```

**推荐**：本插件已经预先定义了若干处理器。你可以选择继承预定义的 `GroupMessageHandler`, `PrivateMessageHandler`, `MessageHandler` 类。建议继承 `__slots__` 属性以优化性能表现。<br>

<br>
**不太推荐**：本插件也提供装饰器以方便将函数转换为处理器实例：`import func_to_Handler`。此时，你的命令创建有如下改变：`handler_list=[mystartfunction],`<br>

## 接管帮助命令

可以通过 `CommandFactory.create_help_command` 方法接管帮助命令，提供自定义的帮助文档：<br>

```python
from nonebot_plugin_ACMD import CommandFactory

# 接管帮助命令
CommandFactory.create_help_command(
    owner='my_plugin',
    help_text='这是我的插件的帮助文档。',
    function=my_custom_help_function
)

# CommandFactory.create_help_command方法没有返回值
```

## 处理器列表

当创建命令时，可以传递一个处理器列表。列表中的每个处理器将按照顺序被指派：<br>

```python
CommandFactory.create_command(
    commands=['/mycommand'],
    handler_list=[FirstHandler(), SecondHandler()],
    owner='my_plugin',
    description='执行一系列操作'
)
```

## 插件热重载

**推荐要求**：仅使用 `ACMD`的方法创建、管理命令和处理器，与 `nonebot`几乎零耦合。<br>

### 启用

启用热重载示例：

```
from nonebot_plugin_ACMD import HotSigner

HotSigner.add_plugin()
```

<br>

无需任何传入变量。`ACMD`将自动分析路径和依赖链<br>

### 依赖链

`ACMD`会在插件重载时自动卸载所有依赖该插件的插件，然后进行重载。这意味着如果一个插件依赖了某个选择启用了**热重置**的插件，它也必须支持**热重载**，否则会导致错误。<br>

这也就是说，`ACMD`的插件热重载具有 **向下的****传染性**。
