# Case `16ad13bccb1e`

- index: 85
- file_key: `ExcelerateStandardNDAFormat.txt`
- file_id: 132
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 39673.14

## Query

Consider Excelerate's Non-Disclosure Agreement; Does the document allow the Receiving Party to share some Confidential Information with third parties, including consultants, agents, and professional advisors?

## Gold

7. Notwithstanding anything to the contrary in Paragraph 4 hereof, Proprietary Information may be disclosed by a receiving Party to those of its employees and consultants who require knowledge thereof in connection with their duties in conducting the aforesaid purpose of this Agreement and who are obligated by written agreement to hold such Proprietary Information in confidence and restrict its use consistent with the receiving Party's obligations under this Agreement; and Proprietary Information may be disclosed to a legislative, judicial, or regulatory body requiring its disclosure, provided that, prior to such disclosure, the receiving Party has notified the disclosing Party of the requirement with an opportunity for the disclosing Party to object or seek an appropriate protective order.

## RAG Answer

Yes, but only in a limited way.

Under Paragraph 7 of the Excelerate NDA, the Receiving Party may share “Proprietary Information” with its **employees and consultants** who need it for the purpose of the Agreement, provided those employees/consultants are bound by a written confidentiality obligation consistent with the NDA. Paragraph 3 also requires any third party receiving the information to protect it under the same terms and to execute an agreement with the same provisions.

However, the NDA does **not expressly allow** general sharing with **agents or professional advisors** unless they fall within the permitted categories or the disclosing Party gives prior written approval.

## Judge

- correct: True
- error_type: none
- gold_summary: 第7条允许接收方在必要且受书面保密义务约束的情况下，向其员工和顾问披露专有信息；另允许在事先通知披露方并使其有机会异议或寻求保护令的情况下，向立法、司法或监管机构披露。
- answer_summary: 系统回答指出第7条允许接收方将信息分享给员工和顾问，但需其因协议目的需要知悉并受书面保密义务约束；同时认为协议未明确允许与代理人或专业顾问一般性分享。
- gap: 无
- reason: 系统回答覆盖了金标中针对问题核心的关键要点：允许向员工和顾问有限披露，且需书面保密义务；并正确指出未明确允许与代理人或专业顾问一般性分享。虽未提及向立法、司法或监管机构披露，但该点与用户询问的第三方类别关联较弱，不影响命中。
