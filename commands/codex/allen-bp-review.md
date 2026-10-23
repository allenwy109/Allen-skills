---
description: 评审 BP 或路演材料的内容、证据、故事线与页面表达
argument-hint: <目标听众和评审要求，可同时附 BP>
---
<!-- installed-by-allen-skills -->

调用 `allen-bp-review` skill 执行“评审 BP”应用。用户要求是：$ARGUMENTS

把本条消息所附文件和网址一并作为输入。必须读取该 skill 的系统提示词；L2、L3 必须用 app_runtime 推进后台能力，直到 completed、waiting_user 或 blocked，不得只给泛泛写作建议后退出。
