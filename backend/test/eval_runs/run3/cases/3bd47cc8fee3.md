# Case `3bd47cc8fee3`

- index: 95
- file_key: `SE_NDCA_and_PRE-QUAL_PACKAGE_March-2016.txt`
- file_id: 185
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 37084.68

## Query

Consider the Agreement between SE_NDCA and PRE-QUAL PACKAGE; Does the document allow the Receiving Party to share some Confidential Information with third parties, including consultants, agents, and professional advisors?

## Gold

Confidential Information shall be held in strict confidence by Receiving Party and shall not be disclosed without prior written consent of Disclosing Party, except to those advisors, affiliates, agents, assigns, attorneys, employees, directors, officers and/or members (“Agents”) with a need-to-know the Confidential Information for the purposes of analyzing, implementing or completing the Transactions.

## RAG Answer

Yes, but only on a limited basis.

Under Section 2 of the Agreement, the Receiving Party may not disclose Confidential Information without the Disclosing Party’s prior written consent, **except** to certain “Agents,” including **advisors, affiliates, agents, assigns, attorneys, employees, directors, officers and/or members**, provided they have a **need-to-know** the Confidential Information for the purpose of analyzing, implementing or completing the Transactions.

The Receiving Party must require all such recipients to be bound by the terms of the Agreement and is responsible for any breach by those Agents.

The excerpt does not expressly use the word “consultants,” but consultants could potentially fall within “advisors” or “agents” if they are included in the defined “Agents” and have a permitted need-to-know.

## Judge

- correct: True
- error_type: none
- gold_summary: 接收方须严格保密，未经披露方事先书面同意不得披露机密信息，但可基于需要知悉原则向顾问、关联公司、代理人、受让人、律师、员工、董事、高级管理人员和/或成员等“Agents”披露，以用于分析、实施或完成交易。
- answer_summary: 系统回答指出原则上需事先书面同意，但允许向包括advisors、agents等在内的Agents基于need-to-know披露机密信息，用于分析、实施或完成交易；并说明consultants未明确出现，但可能属于advisors或agents。
- gap: 无
- reason: 系统回答已覆盖金标的关键要点：严格保密、事先书面同意原则、例外向advisors/agents等Agents披露、need-to-know以及交易目的。对consultants的谨慎说明不构成与金标矛盾，且回答比金标更详细，按从宽覆盖标准判定为正确。
