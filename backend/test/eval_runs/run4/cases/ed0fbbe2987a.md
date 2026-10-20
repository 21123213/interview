# Case `ed0fbbe2987a`

- index: 78
- file_key: `AGProjects-NDA.txt`
- file_id: 113
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 31143.67

## Query

Consider the AGProjects' Non-Disclosure Agreement; Does the document allow the Receiving Party to share some Confidential Information with third parties, including consultants, agents, and professional advisors?

## Gold

The RECEIVING PARTY and its employees, officers, agents and affiliates shall hold the CONFIDENTIAL INFORMATION in confidence and take all reasonable steps to preserve the confidential and proprietary nature of the CONFIDENTIAL INFORMATION, including, without limitation: (i) refraining from disclosing the CONFIDENTIAL INFORMATION to persons within its organization not having a reason to know, and all persons outside its organization unless they have a reason to know and are bound by fiduciary duties of confidentiality to the RECEIVING PARTY; and

## RAG Answer

Yes, but only in a limited way.

Under the AG Projects NDA, the Receiving Party may disclose Confidential Information to persons outside its organization only if those persons:

1. have a reason to know the Confidential Information; and  
2. are bound by fiduciary duties of confidentiality to the Receiving Party.

This means sharing with third parties such as consultants, agents, or professional advisors could be permitted if they need the information for the permitted purpose and are legally bound to keep it confidential. The agreement explicitly mentions agents, employees, officers, affiliates, and outside counsel; it does not separately list “consultants” or “professional advisors,” but they may fall within the general rule for outside persons if the conditions are satisfied.

The NDA also allows limited disclosure when legally compelled, for example in response to a subpoena or legal proceeding, provided the Receiving Party gives prompt notice to the Disclosing Party and discloses only the portion that counsel advises is legally required.

## Judge

- correct: True
- error_type: none
- gold_summary: 金标表明接收方原则上应保密，不得向组织内无需知道的人披露，也不得向组织外人员披露，除非该等人员有知悉必要（reason to know）且对接收方负有保密信托义务（fiduciary duties of confidentiality）。
- answer_summary: 系统回答指出可以有限度地向外部分享，前提是第三方有知悉必要并受保密义务约束；并据此认为顾问、代理人、专业顾问在满足条件时可能被允许接收信息。
- gap: 无
- reason: 系统回答覆盖了金标的关键限制条件和允许披露的核心要点，即外部人员只有在有知悉必要且受保密义务约束时才可接收机密信息。其额外补充内容不影响关键点命中。
