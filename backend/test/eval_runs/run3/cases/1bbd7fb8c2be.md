# Case `1bbd7fb8c2be`

- index: 59
- file_key: `QuickBooks-NDA-template.txt`
- file_id: 180
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 17432.25

## Query

Consider QuickBooks's Non-Disclosure Agreement; Does the document restrict the use of Confidential Information to the purposes stated in the Agreement?

## Gold

The Company and Third Party each agree not to use the Confidential Information disclosed to it by the other party for its own use or for any purpose except to carry out discussions concerning and the undertaking of any business relationship between the two.
Nothing in this Agreement is intended to grant any rights under any patent or copyright of either party, nor shall this Agreement grant either party any rights in or to the other partyʼs Confidential Information, except the limited right to review such Confidential Information solely for the purposes of determining whether to enter into the proposed business relationship between the parties and in carrying out such relationship.
This Agreement shall be binding upon and for the benefit of the undersigned parties, their successors and assigns provided that Confidential Information may not be assigned without consent of the disclosing party.

## RAG Answer

是的。该 QuickBooks NDA 明确限制保密信息的使用目的：接收方不得将保密信息用于自身利益或除“开展双方潜在商业关系的讨论及实施”以外的任何目的；同时约定接收方除本协议规定外无权使用保密信息，且仅可为判断是否进入拟议商业关系及执行该关系之目的审阅保密信息。

## Judge

- correct: True
- error_type: none
- gold_summary: NDA限制双方不得为自身利益或除开展及实施双方潜在商业关系以外的任何目的使用保密信息；仅可为判断是否进入拟议商业关系及执行该关系而审阅保密信息，未授予其他权利。
- answer_summary: 回答指出QuickBooks NDA明确限制保密信息使用目的，接收方不得为自身利益或除开展双方潜在商业关系讨论及实施以外的目的使用；仅可为判断是否进入拟议商业关系及执行该关系审阅保密信息。
- gap: 无
- reason: 系统回答覆盖了金标关于保密信息仅限用于双方商业关系讨论与实施、且不得用于自身利益的核心要点，虽未提及可转让/不得未经同意转让等次要条款，但不影响对问题关键信息的命中。
