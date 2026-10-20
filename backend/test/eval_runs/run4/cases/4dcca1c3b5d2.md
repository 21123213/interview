# Case `4dcca1c3b5d2`

- index: 71
- file_key: `ADVANIDE-NON-DISCLOSURE-AGREEMENT.txt`
- file_id: 111
- file_mapped: True
- correct: **True**
- error_type: `none`
- latency_ms: 18000.92

## Query

Consider ADVANIDE's Non-Disclosure Agreement; Does the document allow the Receiving Party to acquire information similar to the Confidential Information from a third party?

## Gold

1. For the purposes of this Agreement, Information means information relating to one party which is made available by such party to the other party for the Business Purpose, including but not limited to technical documentation, analyses, studies, knowledge and samples but excluding Information which:
III. becomes available to the Receiving Party (as can be demonstrated by the Receiving Party´s written records or other reasonable evidence) from a source other than the Disclosing Party, which source is not bound by any obligation of confidentiality to the Disclosing Party in relation to such Information; or

## RAG Answer

Yes. Under the ADVANIDE Non-Disclosure Agreement, information is excluded from “Information”/Confidential Information if it becomes available to the Receiving Party from a source other than the Disclosing Party, provided that source is not bound by any confidentiality obligation to the Disclosing Party in relation to that information.

The Receiving Party must be able to demonstrate this by written records or other reasonable evidence.

## Judge

- correct: True
- error_type: none
- gold_summary: NDA 将接收方从披露方以外的来源获得、且该来源不受对披露方保密义务约束的信息排除在保密信息之外，接收方需以书面记录或其他合理证据证明。
- answer_summary: 系统回答称允许，并说明信息若来自披露方以外且该来源不受对披露方保密义务约束，则被排除在保密信息之外；接收方需以书面记录或其他合理证据证明。
- gap: 无
- reason: 系统回答覆盖了金标关键要点：第三方/其他来源获取、来源不受保密义务约束、以及需书面记录或合理证据证明，因此判定命中。
