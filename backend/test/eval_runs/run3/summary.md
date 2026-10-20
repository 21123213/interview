# RAG Eval Summary

- overall n=244
- answer_acc=0.9836  （LLM：金标 vs RAG 回答）
- failures=4

> hit@20 不在主评测里计算；对失败题运行 `review_failures` 时会重新提问并写入该指标。

## Per file

| file_key | n | answer_acc |
|---|---:|---:|
| Sony%20Pictures%20Television%20NDA%20(Executed).txt | 16 | 0.9375 |
| RROI_Confidentiality_Agreement_Final.txt | 14 | 1.0 |
| SE_NDCA_and_PRE-QUAL_PACKAGE_March-2016.txt | 14 | 1.0 |
| WEB-NDA-Mutual-Customer-and-Allazo-Electronics-v2.txt | 14 | 1.0 |
| QEP-Williston-Form-of-Confidentiality-Agreement-BMO.txt | 13 | 1.0 |
| Standard%20NDA%20by%20Axial.txt | 13 | 1.0 |
| SupplementOne-NDA.txt | 13 | 1.0 |
| sample-nrel-bilateral-nda-template.txt | 13 | 1.0 |
| Non-Disclosure-NDA-UW-Oshkosh_FINALV2.txt | 12 | 1.0 |
| Roundhouse-Creative-Mutual-NDA.txt | 12 | 1.0 |
| TabunKitchenInvestments-NDA.txt | 12 | 1.0 |
| TSE-TSE-OK-WHK-Mutual-NDA-Fill-in-Blanks-4-29-2019.txt | 11 | 1.0 |
| oceaneering-non-disclosure-agreement.txt | 11 | 1.0 |
| QuickBooks-NDA-template.txt | 10 | 1.0 |
| SINTEC-UK-LTD-Non-disclosure-agreement-2017.txt | 10 | 1.0 |
| WECC_Confidentiality_Agreement.txt | 10 | 1.0 |
| simply-fashion---standard-nda.txt | 9 | 1.0 |
| Petrolube_NDA.txt | 8 | 1.0 |
| Tazza-CAFFE-Confidentiality-Agreement.txt | 8 | 0.875 |
| stony_hill_buyer_nda.txt | 8 | 1.0 |
| thoughtbot-mutual-nda.txt | 7 | 0.8571 |
| NU%20Confidentiality%20Non-Disclosure%20%20Information%20Security%20Agreement%20Final%20....txt | 4 | 0.75 |
| New_York_City_Bar_Association_Model_Form_of_Non-Disclosure_Agreement_2015.txt | 2 | 1.0 |
