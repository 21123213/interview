# Case `0cc16cfe6acf`

- index: 160
- file_key: `lti-two-way-cda-template.txt`
- file_id: 152
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 13527.55

## Query

Consider LTI's Two-Way Confidential Disclosure Agreement; Does the document state that Confidential Information shall only include technical information?

## Gold

1) “Proprietary Information” shall include, but not be limited to, information regarding business matters, know-how, data (technical or non-technical), product samples and specifications, customer information, as well as performance, sales, financial, contractual and special marketing information, ideas, technical data and concepts not previously published or otherwise disclosed to the general public, not previously available without restriction to the receiving Party or others, and which the disclosing Party desires to protect pursuant to this Non-Disclosure Agreement.

## RAG Answer

No. The agreement does not limit confidential/proprietary information to technical information. It defines “Proprietary Information” to include, but not be limited to, business matters, know-how, data (technical or non-technical), product samples and specifications, customer information, performance, sales, financial, contractual and marketing information, ideas, technical data, and concepts.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标指出“Proprietary Information”不仅限于技术信息，而是包括商业事项、know-how、技术或非技术数据、产品样品和规格、客户信息、业绩、销售、财务、合同、市场营销信息、想法、技术数据和未公开概念等。
- answer_summary: 系统回答称协议未将保密/专有信息限定为技术信息，并列举了商业事项、know-how、技术或非技术数据、产品样品和规格、客户信息、业绩、销售、财务、合同、市场营销信息、想法、技术数据和概念等。
- gap: 无
- reason: 系统回答明确否定了“仅包括技术信息”的说法，并覆盖了金标中关于专有信息范围广泛且包含非技术信息的关键要点，因此判定命中。
