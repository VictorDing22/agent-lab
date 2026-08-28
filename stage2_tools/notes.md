# 第 2 关笔记 · README 全部问答

> 对应 `stage2_tools/README.md` 的原理、四个动手任务、验收标准、思考题和常见坑。

---

## 先记住最重要的一句话

**模型不会执行 Python 函数。模型只会返回“请调用哪个工具、使用什么参数”，真正执行函数的是 Agent 程序。**

本关的完整流程：

```text
用户提问
   ↓
Python 把 messages 和工具说明发给模型
   ↓
模型判断是否需要工具
   ├─ 不需要：返回普通文字，Agent 结束
   └─ 需要：返回 tool_calls（工具名称和参数）
                         ↓
                 Python 找到并执行函数
                         ↓
                 把结果作为 role=tool
                 追加到 messages
                         ↓
                 再次请求模型
```

所谓 Agent，核心就是：**模型 + 工具 + 循环调度代码 + 必要护栏**。

---

## 一、本关几个核心概念

### 1. 工具函数是什么？

工具函数是普通的 Python 函数，例如：

```python
def get_supplier_detail(supplier_id: str) -> str:
    ...
```

它可以读取 JSON、查询数据库、请求 Java 接口，也可以调用远程服务。它本身不属于大模型。

### 2. Tool Schema 是什么？

Tool Schema 是一份给模型看的 JSON 说明书，告诉模型：

- 工具叫什么；
- 工具能做什么；
- 可以传哪些参数；
- 哪些参数是必填的；
- 参数应该是什么类型。

例如：

```json
{
  "type": "function",
  "function": {
    "name": "get_supplier_detail",
    "description": "按供应商ID返回详细信息",
    "parameters": {
      "type": "object",
      "properties": {
        "supplier_id": {
          "type": "string",
          "description": "供应商编号，如 S001"
        }
      },
      "required": ["supplier_id"]
    }
  }
}
```

模型看到的是这份说明，不是函数源码。

### 3. 工具注册表是什么？

`TOOLS` 把“模型看到的工具名称”和“程序真正执行的函数”连接起来：

```python
TOOLS = {
    "get_supplier_detail": (
        get_supplier_detail,
        get_supplier_detail_schema,
    )
}
```

其中：

- `TOOLS[name][0]` 是真正的 Python 函数；
- `TOOLS[name][1]` 是发给模型看的 Schema。

名称必须对应。如果 Schema 里叫 `get_supplier_detail`，注册表却没有这个名称，模型提出调用后，程序就找不到函数。

### 4. Tool Calling 是什么？

Tool Calling 是模型和 Agent 程序之间的一套协议，不是模型直接调用代码。

模型可能返回：

```json
{
  "tool_calls": [
    {
      "id": "call_123",
      "function": {
        "name": "get_supplier_detail",
        "arguments": "{\"supplier_id\":\"S001\"}"
      }
    }
  ]
}
```

它表达的是：

```text
请宿主程序帮我调用：
get_supplier_detail(supplier_id="S001")
```

### 5. ReAct 是什么？

ReAct 可以简单理解为：

```text
Reason：分析下一步需要什么信息
Action：请求调用工具
Observation：阅读工具返回结果
再次 Reason
```

本项目没有要求模型把内部思考过程全部打印出来。我们只需要观察它请求了什么工具、参数是什么、工具返回了什么。

---

## 二、任务 1：为什么先写纯 Python 工具？

三个工具必须先脱离模型独立运行：

```python
search_suppliers(category="高压开关")
list_suppliers()
get_supplier_detail("S001")
```

原因是要把问题分层：

- 如果函数单独执行都失败，问题在数据或 Python 代码；
- 如果函数单独成功，接入模型后失败，问题通常在 Schema、参数或 Agent 循环；
- 如果不分层，出现错误时很难判断是模型的问题还是工具的问题。

### 为什么工具返回字符串？

OpenAI 兼容协议中的工具消息最终需要提供可传输的内容。返回字符串最简单：

```python
return json.dumps(supplier, ensure_ascii=False, indent=2)
```

复杂对象也可以先转成 JSON 字符串再交给模型。

### 工具函数必须与模型调用写在同一文件吗？

不需要。只要 Agent 程序能够导入并注册它即可：

```python
from tools.supplier_tools import get_supplier_detail
```

工具还可以是：

- 另一个 Python 文件中的函数；
- 数据库查询；
- Spring Boot 提供的 HTTP 接口；
- 公司采购系统接口；
- MCP Server 暴露的工具；
- 部署在另一台服务器上的服务。

本项目写在同一文件只是为了方便学习。

---

## 三、任务 2：单次工具调用到底发生了什么？

### 第一步：发送工具说明

```python
resp = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    tools=tool_schemas,
)
```

`tools=tool_schemas` 会把工具说明发给模型。

### 第二步：模型决定是否申请调用工具

如果模型认为自己可以直接回答，它返回：

```python
msg.content = "最终答案"
msg.tool_calls = None
```

如果模型需要查询真实数据，它返回：

```python
msg.content = None
msg.tool_calls = [...]
```

### 第三步：Python 解析名称和参数

```python
name = tc.function.name
args = json.loads(tc.function.arguments or "{}")
```

`arguments` 是 JSON 字符串，因此必须通过 `json.loads()` 转成 Python 字典。

### 第四步：Python 执行工具

```python
fn = TOOLS[name][0]
result = fn(**args)
```

例如：

```python
name = "get_supplier_detail"
args = {"supplier_id": "S001"}
```

最终等价于：

```python
result = get_supplier_detail(supplier_id="S001")
```

这一行才是真正执行代码的位置。

### 第五步：把结果交回模型

```python
messages.append({
    "role": "tool",
    "tool_call_id": tc.id,
    "content": result,
})
```

`tool_call_id` 用来说明这个结果对应模型的哪一次调用申请。

在工具结果前，还必须把模型包含 `tool_calls` 的 assistant 消息写入历史：

```python
messages.append(msg.model_dump())
```

完整顺序必须是：

```text
user：查询 S001
assistant：申请调用 get_supplier_detail
tool：返回 S001 的数据
assistant：根据数据生成最终答案
```

如果漏掉中间的 assistant 工具申请，模型就无法正确对应工具结果。

---

## 四、任务 3：完整 Agent 循环

`run_agent()` 使用 `for` 循环，最多执行 `max_steps` 轮：

```python
for step in range(1, max_steps + 1):
    ...
```

每轮只有两种情况。

### 情况 A：模型不再申请工具

```python
if not msg.tool_calls:
    return (msg.content or "").strip()
```

说明模型已经拿到足够信息，可以返回最终答案，函数结束。

### 情况 B：模型申请一个或多个工具

程序会：

1. 保存 assistant 的工具申请；
2. 遍历所有 `tool_calls`；
3. 解析每个工具的名称和参数；
4. 执行对应函数；
5. 把每个结果追加成 `role="tool"`；
6. 进入下一轮，再把完整 messages 发给模型。

### 多步查询示例

问题：

```text
帮我找能供高压开关的供应商，并告诉我哪家历史合作评价最好。
```

模型可能采取以下步骤：

```text
第 1 轮
调用 search_suppliers(category="高压开关")
得到 S001、S003、S006

第 2 轮
调用 get_supplier_detail(supplier_id="S001")
调用 get_supplier_detail(supplier_id="S003")
调用 get_supplier_detail(supplier_id="S006")

第 3 轮
比较三家的历史项目和评价
不再请求工具，返回最终答案
```

代码没有写死“先搜索、再查详情、最后比较”这个顺序。模型根据问题、工具描述和前一步结果决定下一步，这就是这里所说的自主规划。

但自主规划不是无限自主：模型只能使用我们注册的工具，真正的执行权仍然在程序中。

### `max_steps` 为什么必要？

`max_steps=8` 限制的是模型请求轮数，不一定等于工具调用次数。一轮可能包含多个 `tool_calls`。

它可以防止：

- 模型反复调用同一个工具；
- 错误参数导致无限重试；
- 工具之间形成循环；
- 请求耗时和上下文无限增长。

达到上限后返回：

```text
（达到最大步数，未得出最终答案）
```

生产项目还应同时限制单轮工具数、总耗时、单工具超时和总 Token 数。

---

## 五、任务 4：三个刻意破坏实验

### 实验 1：把工具描述改成“函数C”

预期现象：

- 模型不知道这个函数解决什么问题；
- 可能不调用；
- 可能选择错误工具；
- 可能传入不合适的参数。

结论：

> 函数名、description 和参数说明共同构成模型看到的操作界面。说明越准确，模型选对工具和参数的概率越高。

模型没有阅读 Python 源码来补救模糊说明的能力。

实验记录建议：

```text
原描述下的调用：
修改描述后的调用：
是否选对工具：
是否传对参数：
最终答案是否正确：
```

### 实验 2：查询不存在的 S999

当前代码不会抛出异常，而是正常返回：

```text
未找到供应商 S999
```

因此这个实验观察的是：模型收到“未找到”后，是否会停止编造、向用户说明不存在，或者改用搜索工具。

README 中写了“把异常文本原样回填”，但以当前 `solution.py` 实现来说，S999 本身并不会触发异常。

如果要专门测试异常自愈，可以临时让工具抛出异常：

```python
raise ValueError(f"未找到供应商 {supplier_id}")
```

也可以让模型传错参数，触发：

```text
get_supplier_detail() got an unexpected keyword argument ...
```

Agent 捕获异常后不会立即崩溃，而是把错误作为工具结果交给模型：

```python
except Exception as e:
    result = f"工具执行出错: {e}"
```

模型下一轮可能修正参数重新调用，这叫“错误回填后的模型自修正”，但不能保证每次都成功，所以仍然需要步数上限。

### 实验 3：去掉循环上限

可能出现：

```text
模型调用 A
结果不满足
模型调用 B
结果仍不满足
模型再次调用 A
不断重复
```

风险包括：

- 程序长时间不结束；
- 本地模型持续占用 CPU、GPU 和内存；
- 云模型持续产生费用；
- messages 越来越长；
- 外部接口被高频调用；
- 写操作工具可能产生重复副作用。

所以生产系统不能只相信模型会主动停下来，必须由程序设置硬限制。

---

## 六、验收标准口述答案

### 1. 如何口述 Agent 循环？

可以这样回答：

> 首先，Agent 程序把用户问题、对话历史和工具 Schema 发给模型。模型不会直接执行函数，只会返回普通答案或结构化的 tool_calls。如果返回 tool_calls，Agent 程序根据工具名称从注册表找到本地函数，解析参数并执行，再把结果以 role=tool 和对应 tool_call_id 放回 messages。之后再次请求模型，直到模型不再调用工具并给出最终答案，或者达到最大步数。

### 2. 如何判断多步规划成功？

至少观察到：

```text
搜索供应商
   ↓
根据搜索结果取得供应商 ID
   ↓
查询一家或多家详情
   ↓
比较真实工具数据
   ↓
生成最终答案
```

重点不是调用次数越多越好，而是每一步都有必要，并且最终结论能够追溯到工具结果。

### 3. 三个破坏实验应该记录什么？

记录以下内容即可：

- 输入问题；
- 模型请求的工具；
- 模型生成的参数；
- 工具返回或错误；
- 模型是否修正；
- 最终答案是否符合事实；
- 由此需要增加什么护栏。

---

## 七、思考题

### 1. 工具返回的供应商详情很长，全部塞进上下文会怎样？

可能出现：

1. 超过模型上下文窗口；
2. 每轮输入越来越长，推理变慢；
3. 本地模型需要更多内存；
4. 云端模型费用增加；
5. 重要字段被大量无关字段淹没；
6. 模型比较多家供应商时更容易漏看或混淆；
7. 敏感字段被不必要地发送给模型。

控制方法：

- 工具只返回回答当前问题需要的字段；
- 支持 `fields`、分页、条数限制；
- 搜索接口返回摘要，详情接口按 ID 再查；
- 超长文本先分块检索或摘要；
- 大批量排序、计算交给程序完成，只把结果交给模型解释；
- 对工具结果设置最大字符数或 Token 数；
- 敏感字段在进入模型前脱敏或按权限过滤。

不要简单粗暴地截断 JSON，因为可能截掉关键字段或破坏 JSON 结构。更好的方法是在工具层设计精简且结构化的返回值。

### 2. 模型请求了未注册的工具，程序应该怎么办？

不能直接执行，也不能让 `TOOLS[name]` 的 `KeyError` 导致整个 Agent 崩溃。

安全做法：

```python
if name not in TOOLS:
    result = f"未知工具：{name}。可用工具：{list(TOOLS)}"
else:
    fn = TOOLS[name][0]
    result = fn(**args)
```

然后把错误结果交回模型，让它从允许列表中重新选择。

生产环境还应该：

- 只允许调用注册表中的工具；
- 对参数做 Schema 校验；
- 给敏感工具增加权限验证；
- 写操作要求人工确认；
- 记录工具名称、参数、结果和耗时；
- 禁止模型通过字符串动态执行任意 Python 代码。

### 3. 为什么说“工具描述是写给模型看的 UI”？

人类使用软件时会看按钮名称、输入框标签和帮助文字。模型选择工具时看的就是：

- 工具名称；
- `description`；
- 参数名称；
- 参数说明；
- 参数类型；
- required 列表。

清楚的说明：

```text
category：采购品类，如“高压开关”“电线电缆”
keyword：供应商名称中包含的关键词
```

模糊的说明：

```text
category：分类
keyword：关键字
```

模糊说明容易让模型把产品名放到 `keyword`，或者把公司名放到 `category`。

判断命中率不能只凭一次运行。可以准备 20～50 个固定问题，分别使用清楚版和模糊版 Schema，统计：

- 工具选择正确率；
- 参数字段正确率；
- 首次调用成功率；
- 最终答案正确率；
- 平均调用轮数。

这就是最基础的 Agent Eval。

---

## 八、常见坑

### 1. Qwen3 可能输出 `<think>`

思考内容不应当作最终业务答案展示或存入正式结果。使用支持工具调用的模型和兼容模板，并根据 Ollama 模型版本检查返回结构。本项目在 system 中使用 `/no_think`，目的是减少显式思考输出。

### 2. 模型参数不一定是合法 JSON

下面代码避免 JSON 解析错误直接终止程序：

```python
try:
    args = json.loads(tc.function.arguments or "{}")
except json.JSONDecodeError:
    args = {}
```

但直接改成 `{}` 可能继续触发缺少必填参数。更好的生产做法是把“参数不是合法 JSON”的明确错误交给模型，并限制重试次数。

### 3. 工具名称可能不存在

当前代码中的：

```python
fn = TOOLS[name][0]
```

如果 `name` 不存在会触发 `KeyError`，随后被统一捕获并回填。为了日志更清楚，最好显式检查 `name not in TOOLS`。

### 4. 工具结果不一定是字符串

当前打印使用：

```python
result[:200].strip()
```

并且工具消息的 `content` 也需要可传输内容。因此工具最好统一返回字符串，或者调度层执行：

```python
result = json.dumps(result, ensure_ascii=False)
```

### 5. S001 和 S006 是重复企业

这一关先学习 Tool Calling，不处理实体去重。真项目中如果不去重，模型可能把同一家企业当成两家比较。第 8 关会根据统一社会信用代码等稳定标识进行去重。

### 6. “能调用工具”不等于“答案一定正确”

仍然可能发生：

- 选错工具；
- 参数传错；
- 漏查部分供应商；
- 错误理解返回字段；
- 根据真实数据得出错误结论；
- 工具数据本身过期。

因此真项目还需要权限、日志、引用、评测、人工确认和数据治理。

---

## 九、本地模型和工具分别在哪里运行？

本项目模型地址是：

```python
OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
```

表示模型由本机 Ollama 服务运行。三个 Python 工具也由当前 Python 进程在本机执行。

它们虽然都在本机，但仍然是两个部分：

```text
Python Agent 进程
    ↓ HTTP 请求
Ollama 模型服务
    ↓ 返回 tool_calls
Python Agent 进程执行工具
```

如果以后把模型换成云端 API，通常仍然是你的 Agent 后端执行自定义工具，只是问题、工具说明和工具结果会通过网络发送给云端模型。

如果工具部署在远程采购系统中，本地 Python 函数可以通过 HTTP 请求那个系统。模型、Agent 调度程序和业务工具不必部署在同一台机器。

---

## 十、本关三句话总结

1. **Tool Calling 不是模型执行函数，而是模型返回调用申请，Agent 程序负责执行。**
2. **Schema 是模型看到的工具界面，注册表负责把工具名称映射到真正的函数。**
3. **Agent 循环会持续执行“模型决策 → 工具执行 → 结果回填”，直到得到最终答案或触发护栏。**
