# Case `d3f5f01cce3e`

- index: 99
- file_key: `Kenway-NDA-Form-Blank.txt`
- file_id: 148
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 13495.49

## Query

Consider Kenway's Non-Disclosure Agreement; Does the document restrict the use of Confidential Information to the purposes stated in the Agreement?

## Gold

The Recipient shall keep the Disclosing Party's Confidential Information confidential and, except with the prior written consent of the Disclosing Party, shall:
(a) not use or exploit the Confidential Information in any way except for the Purpose;

## RAG Answer

Yes. The document restricts the use of Confidential Information to the purposes stated in the Agreement.

Clause 2.1(a) states that the Recipient shall “not use or exploit the Confidential Information in any way except for the Purpose.” The “Purpose” is defined in the Agreement as the exchange of Confidential Information, trade secrets, know-how and samples to evaluate and pursue potential business arrangements relating to Kenway’s potential supply to the Company.

## Judge

- correct: True
- error_type: none
- gold_summary: NDA规定接收方不得以“Purpose”之外的方式使用或利用保密信息，除非获得披露方事先书面同意。
- answer_summary: 系统回答称文件确实限制保密信息的使用，并引用相同条款：接收方不得以“Purpose”之外的方式使用或利用保密信息；同时补充了“Purpose”的定义。
- gap: 无
- reason: 系统回答明确覆盖了金标的关键要点，即保密信息只能用于协议所述目的；额外解释与金标不矛盾，因此判定命中。
