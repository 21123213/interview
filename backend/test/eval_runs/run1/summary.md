# RAG Eval Summary

- overall n=144
- answer_acc=0.9931  （LLM：金标 vs RAG 回答）
- failures=1

> hit@20 不在主评测里计算；对失败题运行 `review_failures` 时会重新提问并写入该指标。

## Per file

| file_key | n | answer_acc |
|---|---:|---:|
| ExcelerateStandardNDAFormat.txt | 14 | 1.0 |
| Eskom%20Template%20Confidentiality%20and%20Non-disclosure%20Agreement%20Rev%204%20Effective%20August%202017_11.txt | 13 | 0.9231 |
| HNBA-2017-18-Confidentiality-Agreement.txt | 12 | 1.0 |
| EFCAConfidentialityAgreement.txt | 11 | 1.0 |
| Evelozcity%20OESA%20NDA.txt | 11 | 1.0 |
| DBT%20Mutual%20NDA.txt | 10 | 1.0 |
| eulerhermes-nda.txt | 10 | 1.0 |
| CopAcc_NDA-and-ToP-Mentors_2.0_2017.txt | 9 | 1.0 |
| DoiT-ICN-NonDisclosure-Agreement.txt | 9 | 1.0 |
| FNHA-2019RFP-02-NDA-form.txt | 9 | 1.0 |
| Data Use Agreement New York City.txt | 8 | 1.0 |
| Grindrod%20SA%20Confidentiality%20and%20Non-Disclosure%20Undertaking.txt | 8 | 1.0 |
| epsteen_nda.txt | 6 | 1.0 |
| Geheimhaltungsvereinbarung_Abschlussarbeiten_HFU_englisch.txt | 5 | 1.0 |
| GreenStorm%20NDCSC.txt | 5 | 1.0 |
| Focus-Group-APIC-Seattle-Confidentiality-Agreement-031115.txt | 4 | 1.0 |
