# Case `e3edcf56d18c`

- index: 199
- file_key: `NDA-Template-Media-News-Group-inc.txt`
- file_id: 173
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 15079.31

## Query

Consider Media News Group, Inc.'s Non-Disclosure Agreement; Does the document restrict the use of Confidential Information to the purposes stated in the Agreement?

## Gold

3. Recipient shall not, and shall cause its Representatives not to,
(b) use or permit any Confidential Information to be accessed or used for any purpose other than for the evaluation of the Purpose.
The disclosure or receipt of information pursuant hereto in no way obligates either Party to agree to any business transaction, whether or not relating to the Purpose.
10. Neither Party may assign, transfer or sell any of its rights under this Agreement, or delegate any of its obligations hereunder without the prior written consent of the other Party.

## RAG Answer

Yes. The Media News Group, Inc. Non-Disclosure Agreement restricts the use of Confidential Information to the stated Purpose.

Specifically, Section 3 provides that the Recipient may not “use or permit any Confidential Information to be accessed or used for any purpose other than for the evaluation of the Purpose.” The Purpose is defined in the Recitals as assisting the Recipient in evaluating the merits of a potential investment in or other financing of the Disclosing Party.

The Agreement also permits limited exceptions, including disclosure to the Recipient’s Representatives who need to know the information to assist in evaluating the Purpose, authorized disclosure to certain lenders and investors in furtherance of the Recipient’s obligations with respect to the Purpose, and disclosures required by law, subpoena, court order, or governmental demand.

## Judge

- correct: True
- error_type: none
- gold_summary: 协议明确限制接收方不得将保密信息用于评估约定 Purpose 以外的任何目的；并规定披露/接收不强制交易、未经同意不得转让权利义务。
- answer_summary: 系统回答确认协议限制保密信息仅可用于评估约定 Purpose，并引用第3条禁止用于其他目的，同时说明 Purpose 及有限例外。
- gap: 无
- reason: 系统回答覆盖了金标中关于保密信息仅限用于评估约定 Purpose 的关键要点，且未与金标矛盾；额外扩写不影响命中。
