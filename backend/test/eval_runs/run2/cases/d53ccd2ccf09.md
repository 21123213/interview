# Case `d53ccd2ccf09`

- index: 25
- file_key: `IGC-Non-Disclosure-Agreement-LSE-Sample.txt`
- file_id: 141
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 17402.21

## Query

Consider the Non-Disclosure Agreement between IGC and LSE; Does the document restrict the use of Confidential Information to the purposes stated in the Agreement?

## Gold

Each party wishes to disclose to the other party Confidential Information in relation to the Purpose.
The Recipient shall keep the Disclosing Party's Confidential Information confidential and, except with the prior written consent of the Disclosing Party, shall:
(b) Not use or exploit the Confidential Information in any way except for the Purpose.

## RAG Answer

Yes. The Agreement restricts the use of Confidential Information to the stated “Purpose.”

In particular, clause 2.1(b) provides that the Recipient shall **“Not use or exploit the Confidential Information in any way except for the Purpose.”** This restriction is reinforced by:

- **Clause 2.1(d)**: the Recipient may not copy or record Confidential Information except as strictly necessary for the Purpose.
- **Clause 2.2**: the Recipient may disclose Confidential Information to Representatives only if they need to know it for the Purpose.
- **Clause 5.1**: the Disclosing Party authorises the Recipient to use Confidential Information for the Purpose.

The “Purpose” is defined in the Agreement as the specific purpose stated in the document, e.g. evaluation or establishment of a collaboration in respect of a particular project. Therefore, unless otherwise permitted by the Agreement, Confidential Information may only be used for that stated Purpose.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标结论：协议要求接收方对披露方的保密信息保密，并且除事先书面同意外，不得将保密信息用于或开发于约定 Purpose 之外的任何用途。
- answer_summary: 系统回答明确称协议将保密信息的使用限制于 stated “Purpose”，并引用了“Not use or exploit the Confidential Information in any way except for the Purpose”这一关键限制。
- gap: 无
- reason: 系统回答已覆盖金标的关键要点，即保密信息只能用于协议所述 Purpose，且不得用于其他用途；额外扩写不影响命中判定。
