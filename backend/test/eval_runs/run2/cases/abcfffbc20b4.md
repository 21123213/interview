# Case `abcfffbc20b4`

- index: 303
- file_key: `NDA-SqillerBetaTesters.txt`
- file_id: 172
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 14169.98

## Query

Consider the Non-Disclosure Agreement between Sqiller and Beta Testers; Does the document require the Receiving Party to notify the Disclosing Party if they are required by law, regulation, or judicial process to disclose any Confidential Information?

## Gold

Nothing in this Agreement shall prohibit either Party from disclosing a part of the other Party’s Confidential Information if legally required to do so by law or regulation (including those governing capital markets), judicial or governmental order, provided that it gives, to the extent and as soon as legally permissible, prior notice of such disclosure to the other Party.

## RAG Answer

Yes. Under clause 3.7 (“Required Disclosures”), if a Party is legally required to disclose Confidential Information by law, regulation, judicial order, or governmental order, it may do so only if it gives the other Party prior notice of the disclosure to the extent and as soon as legally permissible.

## Judge

- correct: True
- error_type: none
- gold_summary: 若因法律、法规、司法或政府命令要求披露保密信息，协议不禁止该披露，但披露方应在法律允许范围内尽快事先通知另一方。
- answer_summary: 系统回答指出：若因法律、法规、司法或政府命令必须披露保密信息，需向另一方事先通知，且尽可能及时。
- gap: 无
- reason: 系统回答已覆盖金标关键要点：法律要求披露时可披露，但需尽可能及时地事先通知对方；虽表述为‘may do so only if’，与金标‘provided that’在核心通知义务上基本一致。
