# Case `caf878c8c7ae`

- index: 213
- file_key: `sample-nrel-bilateral-nda-template.txt`
- file_id: 184
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 14611.99

## Query

Consider the Non-Disclosure Agreement between NREL and Another Company; Does the document permit the Receiving Party to retain some Confidential Information even after its return or destruction?

## Gold

c. Upon termination of this Agreement, Receiving Party will, within two (2) weeks of written request from Disclosing Party, return all documents concerning the Proprietary Information and NREL Protected Information and all copies of any such documents to Disclosing Party, or certify in writing their destruction, with the exception of copies of Proprietary Information and NREL Protected Information made as a matter of routine information technology or legal backup, provided that such copies will continue to be subject to the confidentiality obligations set forth in this Agreement and may only be used in resolving a dispute between the Parties regarding this Agreement.

## RAG Answer

Yes. Under Section 3(c) of the NREL bilateral NDA, upon termination the Receiving Party must return or destroy all documents and copies of Proprietary Information/NREL Protected Information, **except** for copies retained as a matter of routine information technology or legal backup. Those retained backup copies remain subject to the Agreement’s confidentiality obligations and may only be used to resolve a dispute between the Parties regarding the Agreement.

## Judge

- correct: True
- error_type: none
- gold_summary: 协议终止后，接收方原则上需返还或销毁所有机密文件及副本，但例行信息技术或法律备份产生的副本可以保留；这些保留副本仍受保密义务约束，且仅可用于解决双方关于该协议的争议。
- answer_summary: 系统回答指出允许保留例外情况下的副本，即例行信息技术或法律备份副本；这些副本仍受保密义务约束，并仅可用于解决双方关于协议的争议。
- gap: 无
- reason: 系统回答完整覆盖了金标的关键要点：允许保留例行 IT/法律备份副本、保留副本仍受保密义务约束、用途限于解决协议争议。
