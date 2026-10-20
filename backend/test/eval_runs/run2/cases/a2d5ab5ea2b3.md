# Case `a2d5ab5ea2b3`

- index: 170
- file_key: `lti-two-way-cda-template.txt`
- file_id: 152
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 12199.64

## Query

Consider LTI's Two-Way Confidential Disclosure Agreement; Does the document restrict the use of Confidential Information to the purposes stated in the Agreement?

## Gold

Any Proprietary Information provided by one Party to the other shall be used only in furtherance of the Purpose.

## RAG Answer

Yes. The document restricts use to the stated purpose.

It defines the purpose as a “potential business relationship” (“the Purpose”) and states that “Any Proprietary Information provided by one Party to the other shall be used only in furtherance of the Purpose.” It also limits disclosure to representatives who “need to know such Proprietary Information for the Purpose.”

Note: the template uses the term “Proprietary Information,” not “Confidential Information,” but the restriction applies to that protected information.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标结论是：一方提供给另一方的 Proprietary Information 只能用于推进 Agreement 中所述 Purpose。
- answer_summary: 系统回答确认文档限制信息仅用于 stated purpose，并明确引用了金标原句：Any Proprietary Information provided by one Party to the other shall be used only in furtherance of the Purpose。
- gap: 无
- reason: 系统回答已包含金标的关键信息，且对术语差异（Proprietary Information 与 Confidential Information）进行了补充说明，不影响命中判定。
