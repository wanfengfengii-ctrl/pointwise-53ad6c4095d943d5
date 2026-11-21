# 双仓观测日账修复交接说明

本文件记录夜班核账异常的根因、修复约定与实测结果。README.md 的接口、V1 外层、
异常类型、断言及 `python3 -B -m ledger demo` 演示入口均保持不变。

## 根因

异常链路有两处互相独立的缺陷，均在“取件—签账”环节，分仓报送（`intake`/`revisions`）
本身无缺陷：

1. **取件可固定从未共同生效的版本对（错账 E1/W2 = 24 L）。**
   `exchange/capture.py` 原先在两个独立只读事务里分别读东、西当前修订，读之间
   不做复核。东仓在读后由 E1(7 L) 改为 E2(13 L)、西仓再由 W1(11 L) 改为 W2(17 L)
   时，取件会把东候选 E1 与西候选 W2 拼成一对；该组合在任何时刻都未共同生效。
   隔离仓只复算两级计量，而 E1/W2 的算术和恰好也是 24 L，于是错误签发。
2. **联合依据未绑定实收内容，拼件与同正文换版均可通过。**
   `exchange/witness.py` 的 HMAC 封存范围只有
   `[域标识, issuer_id, pickup_id, day]`，不覆盖两份站件。把早次取件的东站件与
   晚次取件的西站件拼合，或把完整取件的东件换成读数、出处完全相同的新修订，
   封存值不变，隔离仓无法识别。

## 修复内容与交接约定

### 1. 取件只交付本次调用中实际共同生效过的两版（`exchange/capture.py`）

- 一次 `capture` 现在按东→西顺序做两轮读取：
  1. 第一轮为候选读，读完各自在本站读事务结束后运行 `after_read(role, view)`，
     行为与 README 约定一致；
  2. 第二轮为确认读（不触发回调），逐站核对当前修订是否仍等于候选修订。
- 任一仓在两轮之间换版即抛 `CaptureRetry`，不写 `issued` 表、不留固定件；
  调用方可用**原取件号**重试，重试时重新走完整两轮读取。版本指针只会前移，
  因此确认读与候选读为同一修订，即证明该修订在本次调用两次读取的整个窗口内
  持续生效，与另一仓的候选修订构成共同生效对。
- 稳定后重取固定 E2/W2，签出 13 + 17 = **30 L**。
- 站日尚不存在（`NotFound`）仍统一转为 `CaptureRetry`，语义不变。
- 成功取件号的既有约定不变：`read_issued` 领取原件，同号再次发行抛 `Conflict`；
  取件后源仓可继续 `apply` 入账，同正文新报送号仍分配新修订，旧取件内容不变。

### 2. 联合依据绑定确切修订与原序明细（`exchange/witness.py`、`archive/admission.py`）

- `pickup_seal(issuer, pickup_id, day, east_digest, west_digest)` 的 HMAC-SHA256
  封存范围扩为
  `[域标识, issuer_id, pickup_id, day, {east: 东站件摘要, west: 西站件摘要}]`。
- 站件摘要 `exchange.station_piece.piece_digest` 对站件的规范 JSON
  （仓位、站点、站日、**修订号**、报送号、**原序明细的每行读数与逐行出处**、小计）
  取 SHA-256。密钥仍只来自两端本地受信发行配置，不进入交换件。
- `admit` 现在：
  - 证据缺失（`evidence` 为 null）直接 `InvalidData` 拒收；
  - 用**实际收到的两份站件**重算摘要与封存值，常量时间比较；
  - 拼件、同正文换版（修订号变化）、改读数、改出处行号、盗用他件封存、
    未知发行方/错配仓位均在写库前拒收。
- 拒收与提交失败的事务边界未改：`publish_report` 单事务写正式账号、冻结载荷与
  首执，失败整体回滚，不留新账和成功首执；同件重投（JSON 空白/键序不同不影响
  规范比较）复领原账原执，同取件号异件抛 `Conflict`。重开后凭账号经
  `read_report` 取回修订、原序明细、出处、分仓小计与总量。
- V1 外层字段（`version`、`pickup_id`、`day`、`issuer_id`、`east`、`west`、
  `totals`、`evidence`）与 `evidence` 的 `{"seal": ...}` 形状均未变；
  `decode_package` 仍只解码与校验站件，联合受理仍只在 `admit` 发生。
  注意：旧封存格式签出的历史件与新封存互不兼容（封存范围已变），本系统为
  本地单班链路，无既有正式账需要兼容；`freeze_package(..., evidence=None)`
  仍可构造无证据件用于传输层测试，但隔离仓一律拒收。

### 3. 新增回归（`tests/test_evidence.py`，不改动原测试）

- 西仓在读间换版的对称交叉场景：先 `CaptureRetry` 且无固定件/无账，原号重试
  后固定 (E2, W2) 签出 30 L，回调只观察每轮两次候选读；
- 缺失证据拒收且不留账/首执；
- 伪造封存、盗用他号封存拒收；
- 同正文新修订替换、篡改读数（同步改小计）、篡改出处行号均拒收，原件重投仍领
  原账原执。

## 实测结果（Python 3.11 + 标准库 SQLite，仓库根目录）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 完整回归 | `python3 -B check_project.py` | 19 tests，0 failures / 0 errors，PASS |
| INCIDENT 交叉换版 | `python3 -B -m unittest tests.test_handoff.HandoffTests.test_crossed_activation` | PASS，稳定重取签出 30 L |
| INCIDENT 拼件两例 | `python3 -B -m unittest tests.test_archive.ArchiveTests.test_independent_pieces tests.test_archive.ArchiveTests.test_spliced_pair` | PASS，两种来件均拒收且无新账 |
| 交班演示 | `python3 -B -m ledger demo` | T6 场景 7 + 11 = 18 L，源库离线后仍签原账，重开按账号复领、重投得原执 |

另做端到端冒烟验证：取件后源仓继续入账（同正文新报送号得新修订）、同号再发行
`Conflict`、`read_issued` 领原件、新取件绑定新修订、同件重投复领原账原执、
重开 `read_report` 一致，全部符合约定。
