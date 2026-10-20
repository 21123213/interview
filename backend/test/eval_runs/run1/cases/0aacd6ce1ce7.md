# Case `0aacd6ce1ce7`

- index: 5
- file_key: `CopAcc_NDA-and-ToP-Mentors_2.0_2017.txt`
- file_id: 120
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 18408.56

## Query

Consider the Non-Disclosure Agreement between CopAcc and ToP Mentors; Does the document require the Receiving Party to notify the Disclosing Party if they are required by law, regulation, or judicial process to disclose any Confidential Information?

## Gold

If Mentor is required by mandatory, non-appealable judicial or administrative process and/or order to disclose Confidential Information, then Mentor shall promptly notify Organiser and allow Organiser and the Participants reasonable time to oppose such process unless this is not admissible under a mandatory law, judicial or administrative order.

## RAG Answer

Yes. Under Section 7 (“Notice of Required Disclosure”), the Receiving Party (Mentor) must promptly notify the Organiser if Mentor is required by a **mandatory, non-appealable judicial or administrative process and/or order** to disclose Confidential Information. Mentor must also allow the Organiser and the Participants reasonable time to oppose such process, unless doing so is not admissible under a mandatory law, judicial, or administrative order. Mentor may disclose only to the minimum extent required to comply with the order.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标指出：若 Mentor 因强制性、不可上诉的司法或行政程序/命令被要求披露 Confidential Information，Mentor 应及时通知 Organiser，并允许 Organiser 和 Participants 合理时间反对该程序；但若强制性法律、司法或行政命令不允许，则除外。
- answer_summary: 系统回答确认 Receiving Party（Mentor）在因强制性、不可上诉的司法或行政程序/命令被要求披露 Confidential Information 时，必须及时通知 Organiser，并允许 Organiser 和 Participants 合理时间反对，除非强制性法律或命令不允许；还补充了只能按命令要求最小范围披露。
- gap: 无
- reason: 系统回答覆盖了金标的关键要点：通知义务、触发条件（强制性且不可上诉的司法/行政程序或命令）、及时通知、允许合理时间反对，以及法定不允许时的例外。额外信息不构成矛盾，因此判定为命中。
