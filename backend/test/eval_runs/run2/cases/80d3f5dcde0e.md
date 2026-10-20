# Case `80d3f5dcde0e`

- index: 254
- file_key: `NDA-Fintricity-Blank.txt`
- file_id: 166
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 30341.15

## Query

Consider Fintricity's Non-Disclosure Agreement; Does the document allow the Receiving Party to share some Confidential Information with third parties, including consultants, agents, and professional advisors?

## Gold

Each party undertakes in respect of Confidential Information for which it is the recipient:‐
(b) not without the disclosing party's prior written consent in each case to communicate or disclose any part of such Confidential Information to any person except:‐
(ii) the recipient's auditors and professional advisers and any other persons or bodies having a legal right or duty to have access to or knowledge of the Confidential Information in connection with the business of the recipient;

## RAG Answer

Yes, but only in limited circumstances.

Under the NDA, the Receiving Party generally may not disclose Confidential Information to third parties without the Disclosing Party’s prior written consent. However, Clause 3(b) allows disclosure to certain third parties, including:

- the Receiving Party’s **auditors and professional advisers**, and other persons or bodies with a legal right or duty to access the information; and
- **third parties engaged by the Receiving Party** who are concerned with the Business Purpose, but only if they have been **expressly authorised in writing by the Disclosing Party before disclosure**.

This could cover consultants or agents if they are engaged third parties and receive prior written authorisation. The Receiving Party must also ensure that such persons are made aware of the confidentiality obligations and, if requested, sign a separate confidentiality undertaking.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标关键结论是：接收方通常未经披露方事先书面同意不得向任何人披露机密信息，但例外包括接收方的审计师和专业顾问，以及依法有权或有义务接触/知悉机密信息且与接收方业务相关的其他个人或机构。
- answer_summary: 系统回答指出原则上需要披露方事先书面同意，并明确提到允许向接收方的 auditors and professional advisers 以及具有 legal right or duty 接触信息的人披露；同时补充说明 consultants 或 agents 可能作为被授权第三方在事先书面同意下接收信息。
- gap: 无
- reason: 系统回答覆盖了金标中的核心要点：一般禁止未经同意披露，以及审计师、专业顾问和具有法定权利/义务人员属于允许披露对象。其关于 consultants/agents 需要事先书面授权的扩写与金标不矛盾，且多答内容不影响命中判定。
