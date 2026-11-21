# 双仓观测日账交接异常

## 取件期间换版

东仓 E1 为 7 L，西仓 W1 为 11 L。夜班取件读完 E1 后，东仓先提交 E2 的 13 L，西仓再提交 W2 的 17 L，接着取件读到 W2。实际生效过的版本对依次为 E1/W1、E2/W1、E2/W2。隔离仓却给 E1/W2 签了 24 L。三种合法同期合计分别是 18 L、24 L、30 L 中的 18 L、24 L 和 30 L 吗？按版本逐对核算，E2/W1 为 13 + 11 = 24 L，错账 E1/W2 也恰好为 7 + 17 = 24 L。应以实际版本和原明细核账。无法确认共同生效时可返回 `CaptureRetry`，该尝试不留固定件，稳定后重取可签 E2/W2 的 30 L。

```sh
python3 -B -m unittest tests.test_handoff.HandoffTests.test_crossed_activation
```

## 断源后的拼件

将早次取件的东仓站件与晚次取件的西仓站件拼在一起，隔离仓会签发。另一次将完整取件的东件换成同样读值、同样出处的新修订，隔离仓也会签发。两种来件都应拒收且不留新账和首执。指定的完整原件在源仓离线时仍可签账。同件重投复领原账和首执，重开后按原账号可核对修订、原序明细、出处和两级计量。

```sh
python3 -B -m unittest tests.test_archive.ArchiveTests.test_independent_pieces tests.test_archive.ArchiveTests.test_spliced_pair
```

接口和 V1 交换外层见 README.md。完整回归使用 `python3 -B check_project.py`，正常交班演示使用 `python3 -B -m ledger demo`。
