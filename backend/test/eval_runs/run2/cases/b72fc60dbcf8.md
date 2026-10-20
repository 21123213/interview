# Case `b72fc60dbcf8`

- index: 22
- file_key: `IGC-Non-Disclosure-Agreement-LSE-Sample.txt`
- file_id: 141
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 11544.11

## Query

Consider the Non-Disclosure Agreement between IGC and LSE; Does the document permit the Receiving Party to create a copy of some Confidential Information under certain circumstances?

## Gold

(d) Not copy, reduce to writing or otherwise record the Confidential Information except as strictly necessary for the Purpose (and any such copies, reductions to writing and records shall be the property of the Disclosing Party).

## RAG Answer

Yes. Under Clause 2.1(d), the Receiving Party is generally prohibited from copying Confidential Information, but it may make copies where strictly necessary for the Purpose. Any such copies remain the property of the Disclosing Party.

## Judge

- correct: True
- error_type: none
- gold_summary: 接收方不得复制、书面记录或以其他形式记录保密信息，除非严格为特定目的所必需；且任何此类复制件、书面记录和记录均属于披露方所有。
- answer_summary: 系统回答指出依据 Clause 2.1(d)，接收方通常不得复制保密信息，但可在严格为特定目的所必需时制作副本，且副本仍属于披露方。
- gap: 无
- reason: 系统回答完整覆盖了金标中的关键要点：一般禁止复制，但允许在严格为特定目的所必需时复制，并说明复制件归披露方所有。
