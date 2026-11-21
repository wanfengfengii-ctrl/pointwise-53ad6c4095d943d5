# 区域观测日账仓

东、西分仓各自接收登记簿上的观测值。夜班从两仓取交接件，异地核账员验收并签发正式日账。正式账号可以查回两侧修订、原序明细、逐行出处、小计与区域总量。

## 运行

需要 Python 3.11 和标准库 SQLite。在项目根目录运行：

```sh
python3 -B check_project.py
python3 -B -m ledger demo
```

`check_project.py` 由运行平台提供。完整测试位于 `tests` 包中，亦可执行 `python3 -B -m unittest discover -s tests -t .`。演示读取 `samples` 中的两份登记簿材料，在临时目录里录入东仓 5 L、缺测、实测 0 和西仓 11 L。东仓更正为 7 L 后取件。两站随后再次推进，源库移出运行路径，隔离仓仍签出原来的 7 L、11 L 和 18 L，重开后按账号领取并复投取回首执。

## 分仓日表

下面的 API 可从 `ledger` 导入。每个库使用独立 SQLite 文件。各入口自行关闭 SQLite 连接，库句柄可在多次操作间复用。库文件的上级目录由调用者创建。站库处于业务使用期间时应保留同一文件，日表更新通过 `apply` 提交。

```python
from ledger import apply, init, read_site

east = init('east.sqlite', 'east')
revision = apply(east, {
    'station': 'east',
    'day': '2030-04-09',
    'submission_id': 'E-001',
    'rows': [
        {'litres': 7, 'origin': {'register': '东站簿甲', 'line': 1}},
        {'litres': None, 'origin': {'register': '东站簿甲', 'line': 2}},
        {'litres': 0, 'origin': {'register': '东站簿甲', 'line': 3}},
    ],
})
current = read_site(east, '2030-04-09')
historical = read_site(east, '2030-04-09', revision.revision)
```

站日使用 `YYYY-MM-DD`，标识与登记簿名使用非空白文本，出处行号为正整数。读数为整数升或 `None`，JSON 中缺测写作 `null`。缺测和实测零各保留原位置及原出处。`rows: []` 表示已报送的空日，小计为 0 L。总量用整数计算，SQLite 中的读数和汇总不经浮点转换。

`init` 重开时保留已有报送和更正，站点身份不同会拒绝。每次更正提交同站同日的完整替换行并使用新报送号。新的报送即使正文相同也分配新修订。旧修订继续可读。精确重送原报送返回对应的既有修订，并保留当时已经生效的当前指针。复用报送号且站日、行序、读数或出处发生变化则报冲突。报送、修订和当前指针在同一次提交中生效。

## 取件与隔离签账

```python
from ledger import (
    IssuedStore, TrustedIssuer, admit, capture, encode_package,
    init, open_archive, read_report,
)

# 发行端和隔离仓各从本地配置取得约定的发行身份和密钥。
# shared_key 为调用者配置的至少 32 字节密钥。
issuer = TrustedIssuer('regional-night', shared_key, 'east', 'west')
west = init('west.sqlite', 'west')
issued = IssuedStore('issued.sqlite')
package = capture(issued, issuer, 'P-001', '2030-04-09', east, west)
wire = encode_package(issued.read_issued(package.pickup_id))

archive = open_archive('archive.sqlite')
report, receipt = admit(archive, wire, {'regional-night': issuer})
frozen = read_report(archive, receipt.account_no)
```

示例假设调用者已经报送目标日的两侧日表。站点身份由发行配置分别绑定到东、西仓位，两站可以有相同的本地修订号。一次新取件绑定该次调用中实际共同生效的两份修订。换版期间若本次无法确认共同生效，返回 `CaptureRetry`，同号可再次尝试。已成功取件的编号由 `read_issued` 领取原件，再次以该号发行会报冲突。`capture` 可接收关键字参数 `after_read(role, view)`，用于观察两次候选站读的完成。回调在对应的本站读事务结束后运行。

交接件使用 UTF-8 JSON。V1 外层包含 `version`、`pickup_id`、`day`、`issuer_id`、`east`、`west`、`totals` 和 `evidence`。站件保存仓位、站点、站日、修订、报送号、原序明细和小计。`totals` 分别保存 `east_litres`、`west_litres`、`total_litres`。联合依据由受信现场发行，隔离仓按本地配置验收，传输方应原样转交。`decode_package` 只负责解码和站件校验，`admit` 才提供联合受理。配置和密钥独立于交换件，密钥通过约定渠道配置到两端。

隔离仓核对确切两份实收数据及联合依据，复算两级计量，随后事务内登记正式账号、冻结日账和首执。`admit` 接受 JSON 字节或字符串，返回 `(Report, Receipt)`。重投同一规范内容返回原账和原执，JSON 空白与对象键排列不影响比较。同取件号的另一合法固定件报 `Conflict`。拒收和提交失败均无新增日账或首执。`read_report` 只使用隔离仓的正式账号和已提交记录。

接口失败以异常表示。`InvalidData` 表示非法报送或交接件，`IdentityError` 表示站点身份不符，`NotFound` 表示未知站日、修订、取件号或账号，`Conflict` 表示编号复用冲突，`CaptureRetry` 表示本次未固定可用版本对，`StorageError` 表示 SQLite 操作或提交失败。库操作失败会退出该次事务。
