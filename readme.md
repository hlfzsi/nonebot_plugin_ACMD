# nonebot_plugin_ACMD

## 项目简介
本项目旨在为基于 NoneBot 框架开发的聊天机器人提供一套灵活且强大的命令处理机制。通过定义命令、处理器以及帮助文档，可以轻松地扩展机器人的功能，同时保证代码的整洁性和可维护性。<br>

## 功能特点
- **命令管理**：支持创建、更新和删除命令，每个命令可以关联多个处理器。<br>
- **处理器机制**：处理器是执行命令逻辑的核心组件，可以通过继承 `BasicHandler` 并实现 `handle` 方法来定义特定的处理器。<br>
- **帮助文档**：提供自动生成帮助文档的功能，支持按插件所有者分页显示命令，亦可选择由插件接管帮助文档。<br>
- **异步数据库与连接池**：使用 `aiosqlite` 进行异步数据库操作，确保在处理大量请求时仍能保持良好的性能。<br>

## 安装依赖
安装项目所需的所有依赖项，可以通过运行以下命令完成：<br>
```
pip install pandas
pip install aiosqlite
```

## 快速开始
**注意**：不要二次调用 `dispatch` 函数，本插件已经完成了它的调用。<br>
本 README 仅提供大致介绍，详细调用见代码注释。在 `command.py` 文件最下方，有一个已经定义好的处理器可作为示例。<br>

## 自带命令
- `/help` 由 ACMD 自动生成帮助文档/由接管者提供文档<br>
- 完整指令：`/help [owner] [page]`<br>

## 创建命令
要创建一个新的命令，你可以使用 `CommandFactory.create_command` 方法：<br>
```python
from nonebot_plugin_ACMD import CommandFactory

# 创建一个简单的命令
CommandFactory.create_command(
    commands=['/start'], 
    handler_list=[MyStartHandler()],
    owner='my_plugin',
    description='启动机器人',
    full_match=True
)
```

## 定义处理器
处理器需要继承自 `BasicHandler` 并实现 `handle` 方法。例如：<br>
```python
from nonebot_plugin_ACMD import BasicHandler

class MyStartHandler(BasicHandler):
    async def handle(self, bot, event, msg, qq, groupid, image, **kwargs):
        await bot.send(event, "Hello! I'm your assistant.")
```

**推荐**：本插件已经预先定义了若干处理器。你可以选择继承预定义的 `GroupMessageHandler`, `PrivateMessageHandler`, `MessageHandler` 类。建议继承 `__slots__` 属性以优化性能表现。<br>
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
```

## 高级特性
### 处理器列表
当创建命令时，可以传递一个处理器列表。列表中的每个处理器将按照顺序被指派：<br>
```python
CommandFactory.create_command(
    commands=['/mycommand'],
    handler_list=[FirstHandler(), SecondHandler()],
    owner='my_plugin',
    description='执行一系列操作'
)
```

### 自定义帮助文档
通过 `create_help_command` 方法，可以为你的插件提供自定义的帮助文档。这允许你根据插件的特性和用户需求来调整帮助信息。<br>

### 错误处理
在处理器中，建议添加适当的错误处理逻辑，以确保即使在异常情况下也能给出友好的反馈或日志记录。<br>

## 贡献指南
欢迎任何有兴趣的朋友贡献代码或提出建议！如果你发现了 bug 或有新的功能想法，请随时提交 issue 或 pull request。<br>