# Case `0cce6cd3d19c`

- index: 7
- file_key: `Non-Disclosure-NDA-UW-Oshkosh_FINALV2.txt`
- file_id: 175
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 20221.89

## Query

Consider the Non-Disclosure Agreement between University of Wisconsin Oshkosh; Does the document indicate that the Agreement does not grant the Receiving Party any rights to the Confidential Information?

## Gold

7. The Receiving Party expressly acknowledges that the Disclosing Party owns the Confidential Information they disclose, and that the transmission by the Disclosing Party of their Confidential Information (or any third party’s Confidential Information entrusted to the Disclosing Party) shall not be construed to grant the Receiving Party any patent, know-how, copyright, trade secret, trademark, or other intellectual property rights in, or arising from, the Confidential Information disclosed. If any such rights are to be granted to the Receiving Party, such grant shall be expressly set forth in a separate written instrument.

## RAG Answer

Yes. Section 7 of the Non-Disclosure Agreement states that the transmission of Confidential Information “shall not be construed to grant the Receiving Party any patent, know-how, copyright, trade secret, trademark, or other intellectual property rights in, or arising from, the Confidential Information disclosed.” It also provides that if any such rights are to be granted, they must be expressly set forth in a separate written instrument.

However, the Agreement does authorize the Receiving Party to use Confidential Information for the stated Purpose or Project under Section 8, so it does not grant intellectual property rights, but it does permit limited use.

## Judge

- correct: True
- error_type: none
- gold_summary: 第7条明确：传输保密信息不应被解释为授予接收方任何专利、专有技术、版权、商业秘密、商标或其他知识产权；如有授予，须以单独书面文件明确。
- answer_summary: 系统回答确认协议不授予接收方知识产权，并引用第7条说明传输保密信息不构成授予任何专利、专有技术、版权、商业秘密、商标或其他知识产权；同时补充若授予需单独书面文件。
- gap: 无
- reason: 系统回答覆盖了金标的关键结论，即协议不授予接收方任何知识产权，且任何授予需单独书面文件；额外关于第8条有限使用的说明不与金标矛盾。
