# Case `f61e8ebdf5ba`

- index: 123
- file_key: `LiiON%20NDA%202-27-2015%20v1.0.txt`
- file_id: 151
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 52271.35

## Query

Consider LiiON's Non-Disclosure Agreement; Does the document allow the Receiving Party to acquire information similar to the Confidential Information from a third party?

## Gold

3. Inapplicability of Restrictions. There shall be no restrictions under this Agree-ment with respect to any portion of the Confidential Information which:
(e) is furnished to any third party by Disclosing Party without a similar re-striction on the third party’s rights.

## RAG Answer

Not expressly. The LiiON NDA does not contain a clause specifically permitting the Receiving Party to acquire information similar to Confidential Information from a third party.

However, the agreement restricts only the use or disclosure of Confidential Information received from the Disclosing Party. Under Section 3, restrictions do not apply to information that is, for example:

- independently developed by the Receiving Party without breach of the NDA;
- publicly known through no wrongful act of the Receiving Party;
- already known to the Receiving Party without breach;
- furnished to a third party by the Disclosing Party without a similar restriction.

So, acquiring similar information from a third party is allowed only if that information is not Confidential Information subject to the NDA or falls within one of these exclusions. It does not permit the Receiving Party to use or disclose actual Confidential Information received from the Disclosing Party in violation of the agreement.

## Judge

- correct: True
- error_type: none
- gold_summary: NDA 第3条规定，若披露方将某部分保密信息提供给第三方，且未对该第三方施加类似限制，则该部分信息不受本协议限制。
- answer_summary: 系统回答指出 Section 3 的例外包括“furnished to a third party by the Disclosing Party without a similar restriction”，并说明从第三方获取类似信息仅在属于该等例外或不属于受 NDA 约束的保密信息时才被允许。
- gap: 无
- reason: 尽管系统回答开头称没有明确允许，但其后续准确覆盖金标关键要点，即披露方向第三方提供且无类似限制时相关保密信息不受限制；按从宽覆盖标准可判命中。
