# RAG Eval Summary

- overall n=244
- answer_acc=0.9713  （LLM：金标 vs RAG 回答）
- failures=7

> hit@20 不在主评测里计算；对失败题运行 `review_failures` 时会重新提问并写入该指标。

## Per file

| file_key | n | answer_acc |
|---|---:|---:|
| amc-general-mutual-non-disclosure-agreement-en-gb.txt | 15 | 1.0 |
| 01_Bosch-Automotive-Service-Solutions-Mutual-Non-Disclosure-Agreement-7-12-17.txt | 14 | 1.0 |
| eHandshake_Non_Disclosure_Agreement.txt | 14 | 0.8571 |
| wayne-fueling-systems-mutual-non-disclosure-agreement-final.txt | 14 | 1.0 |
| Mutual-Non-Disclosure-Agreement-Inventor-Product-Development-Experts-Inc..txt | 13 | 1.0 |
| NDA-Template-Media-News-Group-inc.txt | 13 | 0.8462 |
| NDA_Street_Stream_Franchise.txt | 13 | 0.9231 |
| tpi-non-disclosure-agreement_1.txt | 13 | 0.9231 |
| 5-NSK-Confidentiality-Agreement-for-Suppliers.txt | 12 | 1.0 |
| AfriGIS_Client-NDA_Template_2019.txt | 11 | 0.9091 |
| Aspiegel_NDA_template.txt | 11 | 1.0 |
| BCG-Mutual-NDA.txt | 11 | 1.0 |
| ceii-and-nda.txt | 11 | 1.0 |
| AGProjects-NDA.txt | 10 | 1.0 |
| UALR-Standard-Non-disclosure-AgreementTemplate.txt | 10 | 1.0 |
| BT_NDA.txt | 9 | 1.0 |
| NDA_ResConnect.txt | 9 | 1.0 |
| VELCO%20NDA%20rev0%20Dec%2014%202015.txt | 9 | 1.0 |
| ADVANIDE-NON-DISCLOSURE-AGREEMENT.txt | 7 | 1.0 |
| vmw-certification-conduct-policy.txt | 6 | 1.0 |
| 12032018_NDA_The%20Munt_EN.txt | 5 | 1.0 |
| Data_Use_and_Non_Disclosure_Data_Disclosed_to_MDCH_Trauma_Registry_Final_465518_7.txt | 4 | 1.0 |
| SAMED%20confidentiality%20non%20disclosure%20and%20conflict%20of%20interest%20agreement%20for%20board%20and%20committee%20members%20ver%201.txt | 3 | 1.0 |
| thoughtbot-mutual-nda.txt | 3 | 1.0 |
| CBP%20Non-Disclosure%20Form_October2018.txt | 2 | 1.0 |
| dhs-nda.txt | 2 | 1.0 |
