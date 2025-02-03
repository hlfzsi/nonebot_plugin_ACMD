<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-ACMD

_✨ 另一个插件开发方案 ✨_

<a href="./LICENSE">
    <img src="https://img.shields.io/pypi/l/nonebot-plugin-ACMD" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-ACMD">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-ACMD.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">

</div>

</details>
nonebot-plugin-ACMD 是一个支持 用户输入纠错、指令热修改 的另一个插件开发方案。

* [X]  用户输入纠错与自动补全
* [ ]  ~~热重载 ~~（尚无计划）
* [X]  指令热修改
* [X]  命令行指令与自动补全
* [X]  依赖注入

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

```
nb plugin install nonebot-plugin-ACMD
```

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

```
pip install nonebot-plugin-ACMD
```

</details>
<details>
<summary>pdm</summary>

```
pdm add nonebot-plugin-ACMD
```

</details>
<details>
<summary>poetry</summary>

```
poetry add nonebot-plugin-ACMD
```

</details>
<details>
<summary>conda</summary>

```
conda install nonebot-plugin-ACMD
```

</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

```
plugins = ["nonebot_plugin_ACMD"]
```

</details>

## ⚙️ 配置

在 nonebot2 项目的 `.env`文件中添加下表中的配置


|     配置项     | 必填 | 默认值 |                  说明                  |
| :-------------: | :--: | :----: | :------------------------------------: |
| similarity_rate |  是  |  75.0  | 相似度阈值，只有高于阈值的输入会被纠正 |

## 🎉 使用

### 自带指令


|         指令         |  权限  | 需要@ | 范围 |          说明          |
| :------------------: | :----: | :---: | :--: | :--------------------: |
| /help [model] [page] | 所有人 |  否  | 全域 | 返回ACMD生成的帮助文档 |

## 📖 介绍 / 开发说明

**如果你只是一般用户而非开发者，后续内容无需阅读**

本文档选取部分ACMD顶层所导入的模块进行介绍。

### 实际案例

参阅本项目根目录下example。如图为example实际运行效果。建议在阅读后面的文档时与example进行比对。

![1737942838201](images/readme/1737942838201.png)

### ACMD_get_driver方法

```python
from nonebot_plugin_ACMD import ACMD_get_driver
driver = ACMD_get_driver()
```

> **Warning** : ACMD的driver和nonebot的driver完全不同，ACMD仅仅提供了注册启动函数和注册回收函数两个方法

为什么使用ACMD的driver？

ACMD的driver为ACMD的依赖注入和热重载设计，如果你不需要以上两个功能，完全不需要使用ACMD的driver。

#### on_startup

被装饰函数不接受任何传入。装饰器不接受任何传入。

#### on_shutdown

被装饰函数不接受任何传入。装饰器不接受任何传入。

### ~~HotSigner~~

~~这是ACMD的热重载实现模块。~~

**已废弃**

```python
from nonebot_plugin_ACMD import HotSigner
HotSigner.add_plugin()
```

~~不需要传入。ACMD将自动分析。需要注意，ACMD的热重载具有传染性。如果你的依赖链中有任何一个插件启用了热重载，你的插件也必须支持热重载，否则可能导致不可预料的后果。~~

### BasicHandler

这是整个ACMD处理过程的核心对象。

```python
from nonebot_plugin_ACMD import BasicHandler
```

所有的处理器都应当继承自BasicHandler。

它的实现如下：

```python
class BasicHandler(ABC, metaclass=SingletonABCMeta):
    """处理器基类

    - 必须实现异步方法 handle

    - 属性:
        - block (bool): 是否阻断传播,默认为True
        - handler_id (int): 处理器ID,由HandlerManager自动分配
        - unique (str): 处理器唯一标识符,可用于测试辨识,默认为None

    - 可使用的方法:
        - is_PrivateMessageEvent 判断当前消息事件是否为私聊消息
        - get_self_id 获取当前处理器实例的处理ID
        - get_handler_by_id 通过处理ID获取处理器实例
        - get_handler_id 通过处理器实例获取处理ID


    - 推荐重写方法 (按执行顺序排列) :
        - should_handle 异步  该处理器是否应当执行 , 必须返回bool
        - should_block 异步  该处理器是否阻断传播 , 必须返回bool
    """
    __slots__ = ('block', '_handler_id', 'unique', 'parameters', '__weakref__')

    def __init__(self, block: bool = True, unique: str = None, **kwargs):
        self.block = block
        self._handler_id: int = HandlerManager.get_id(self)
        self.unique = unique
        self.parameters = HandlerContext.analyse_parameters(self)

    @abstractmethod
    async def handle(self, bot: Bot = None, event: Union[GroupMessageEvent, PrivateMessageEvent] = None, msg: UserInput = None, qq: PIN = None, groupid: GroupID = None, image: ImageInput = None) -> None:
        """
        传入参数详见Atypes
        """
        pass

    @staticmethod
    def is_PrivateMessageEvent(event: Union[GroupMessageEvent, PrivateMessageEvent]):
        return event.message_type == 'private'

    async def should_handle(self) -> bool:
        return True

    async def should_block(self) -> bool:
        return self.block

    def get_self_id(self) -> int:
        return self.handler_id

    @staticmethod
    def get_handler_by_id(handler_id: int) -> Optional['BasicHandler']:
        return HandlerManager.get_handler(handler_id)

    @staticmethod
    def get_handler_id(handler: 'BasicHandler') -> int:
        return HandlerManager.get_id(handler)

    @property
    def handler_id(self) -> int:
        return self._handler_id

    def remove(self):
        HandlerManager.remove_handler(self)
        with SingletonABCMeta._lock:
            if type(self) in SingletonABCMeta._instances and SingletonABCMeta._instances[type(self)] is self:
                del SingletonABCMeta._instances[type(self)]

    def __str__(self):
        if self.unique:
            return f'{self.unique}'
        else:
            return f'{self.__class__.__name__}'
```

我们可以清晰地看到，BasicHandler采取了单例模式，即一个类只能产生一个实例。

对于BasicHandler，ACMD预先定义了一些处理器基类。

```python
from nonebot_plugin_ACMD.already_handler import MessageHandler, GroupMessageHandler, PrivateMessageHandler
```

它们分别是：没有过滤的Handler（BasicHandler换皮），只处理群聊消息，只处理私聊消息。

对于一些需要灵活性而不过多需要拓展性的项目，ACMD提供了装饰器方法将一个异步函数转换为BasicHandler实例。

```python
from nonebot_plugin_ACMD import func_to_Handler
```

这里特别介绍`message_handler`装饰器。

这个装饰器允许你混入任意一个自行定义的Handler，这允许在保持灵活性的基础上不损失太多拓展性。

此外，所有装饰器都接受`block` `unique`参数，它们的作用与在BasicHandler中的作用相同。

与BasicHandler类似，ACMD也预先定义了一些具有过滤作用的装饰器。

### command

这里是联系处理器与派发的桥梁。

```python
from nonebot_plugin_ACMD import CommandFactory, Command
```

#### Command

`Command`是ACMD的命令对象，它允许你在运行时修改指令。

通常，每创建一个指令，就会返回一个`Command`对象。创建指令的方法将在稍后提及。

运行时修改指令的推荐做法是使用`updata`方法。

#### CommandFactory

创建指令。

不废话，贴代码。

```python
class CommandFactory:
    """
    工厂类,包含所有创建命令所需要的方法

    P.S 该类设计并不符合工厂类规范
    """
    @staticmethod
    def create_command(commands: Optional[List[str]] = None, handler_list: Union[str, int, BasicHandler, List[Union[str, int, BasicHandler]]] = None, owner: Optional[str] = None, description: Optional[str] = '', full_match: bool = False) -> Optional[Command]:
        """创建命令对象。

        Args:
            commands (List[str]): 命令列表。不传入或传入`None`代表无需命令，总是触发。
            handler_list (str, int, BasicHandler, List[str, int, BasicHandler]): 处理器单例或列表
            owner (str): 所有者, 用于标识指令所属插件
            description (str, optional): 描述. Defaults to ''.
            full_match (bool, optional): 是否完全匹配. Defaults to False.

        Returns:
            Command: 命令对象
        """
        if handler_list is None:
            raise RuntimeError("没有处理器传入")

        if not isinstance(handler_list, list):
            handler_list = [handler_list]

        caller_frame = inspect.stack()[1]
        script_folder_path = os.path.abspath(
            os.path.dirname(caller_frame.filename))

        if commands is None:
            for handler in handler_list:
                HandlerManager.set_Unconditional_handler(handler)
            return None

        if owner is None:
            raise RuntimeError(f"命令 {commands} 没有指定拥有者")

        return Command(commands, description, owner, full_match, handler_list, script_folder_path=script_folder_path)

    @staticmethod
    def create_help_command(owner: str, help_text: str = '', function: Callable = None) -> None:
        """接管帮助命令。

        Args:
            owner (str): 被接管插件对象
            help_text (str): 帮助文本
            function (Callable, optional): 帮助命令处理函数. Defaults to None.可返回字符串,也可返回None

            通常情况下,help_text与function选择一个传入即可,function优先级更高.
        """
        HelpTakeOverManager.takeover_help(owner, help_text, function)


    @staticmethod
    def parameter_injection(field: str, field_type: type):
        """
        装饰器用于设置依赖关系，确保可以被解析并由handler调用。

        参数:
            field (str): 新字段的名称。
            field_type (type): 新字段的类型。
        """
        def decorator(func):
            # 检查func是否为协程函数
            if not inspect.iscoroutinefunction(func):
                raise RuntimeError("被装饰函数必须是异步的")

            HandlerContext.insert_field(field, field_type, func)

            async def wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                return result

            return wrapper

        return decorator
```

大体上，只需要阅读方法的文档字符串即可。

特别地，如果`create_command`方法的`commands`参数传入为None，该处理器会被作为一个无条件处理器，即只要有消息则必定响应。

### Atypes

ACMD的类型提示模块。

依赖注入基于Atypes实现。

```python
import nonebot_plugin_ACMD.Atypes
```

通常，你需要使用Atypes的若干类型，包括：`UserInput` `GroupID` `ImageInput` `Record` `PIN` 。

具体请阅读Atypes各类型的文档字符串，它们非常详细。

特别地，`ImageInput`类提供了 单/批量 图片下载方法。
