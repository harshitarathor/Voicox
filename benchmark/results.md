# Voicox benchmark (2026-11-10)

30 questions, 20 of them spoken into a microphone (the rest were typed).

| Measure | Result |
|---|---|
| Speech understood (Gnani Prisma) | 100% |
| Question turned into the right query | 93% |
| Answer equals the raw-data figure | 93% |

## By language

| Language | Correct answers |
|---|---|
| Hinglish | 100% |
| Hindi | 100% |
| English | 60% |
| Noisy | 100% |

## Every question

| # | Group | Question | Input | Heard | Result |
|---|---|---|---|---|---|
| h01 | hinglish | Pichle mahine sabse zyada kya bika | audio | pichle mahine sabse zyada kya bikka? | correct |
| h02 | hinglish | Is hafte ki bikri kitni hui | audio | Is hafte ki bikri kitni hui? | correct |
| h03 | hinglish | Kal kitna sales hua | typed |  | correct |
| h04 | hinglish | Doodh ki bikri pichle mahine kitni thi | audio | dooh ki bikri pichle mahine kitni thi? | correct |
| h05 | hinglish | Chawal ka stock kitna hai | audio | chaval ka stock kitna hai? | correct |
| h06 | hinglish | Kaun sa saman kam bach gaya hai | audio | Kaun sa saman kam bach gaya hai? | correct |
| h07 | hinglish | Stock mein kya mismatch hai | typed |  | correct |
| h08 | hinglish | Chawal mein gap kyun hai | audio | Chaval mein gap kyun hai? | correct |
| h09 | hinglish | Doodh mein gap kyun hai | typed |  | correct |
| h10 | hinglish | Pichle hafte aur is hafte ki bikri compare karo | audio | pichle hafte aur is hafte ki bikri compare karo. | correct |
| h11 | hinglish | Sabse kam bikne wala product kaun sa hai | typed |  | correct |
| h12 | hinglish | Kis item mein sabse zyada damage hua | audio | Is item mein sabse zyada damage hua. | correct |
| h13 | hinglish | Aaj kitni bikri hui | typed |  | correct |
| h14 | hinglish | Is mahine ka revenue batao | typed |  | correct |
| d01 | hindi | पिछले महीने सबसे ज्यादा क्या बिका | audio | pichle mahine sabse zyada kya bikka? | correct |
| d02 | hindi | इस हफ्ते की बिक्री कितनी हुई | audio | is hafte ki bikri kitni hui? | correct |
| d03 | hindi | चावल में गैप क्यों है | audio | chaval mein gap kyun hai? | correct |
| d04 | hindi | कौन सा सामान कम बचा है | audio | Kaun sa saman kam bach gaya hai? | correct |
| d05 | hindi | दूध की बिक्री कितनी हुई | typed |  | correct |
| e01 | english | Which product sold the most last month | audio | Which product sold the most last month? | correct |
| e02 | english | What were the total sales this week | audio | What were the total sales this week? | correct |
| e03 | english | Why is rice short | audio | Wise rice shot. | WRONG: app said: I did not understand that question. Try asking: 'Which product sold the most last month?' |
| e04 | english | Show me low stock items | audio | Show me low cost items. | WRONG: app said: I did not understand that question. Try asking: 'Which product sold the most last month?' |
| e05 | english | Compare this week with last week | typed |  | correct |
| n01 | noisy | Sabse zyada bikne wala item kaun sa hai | audio | sabse zyada bikne wala item kaun sa hai? | correct |
| n02 | noisy | Tel mein gap kyun hai | audio | tel mein gap kyun hai? | correct |
| n03 | noisy | Low stock wale items dikhao | audio | low stock wale item dikhao. | correct |
| n04 | noisy | Is hafte ki bikri pichle hafte se kitni badli | audio | Is hafte ki bikri pichle hafte se kitni badli? | correct |
| n05 | noisy | Cheeni ka stock kitna hai | typed |  | correct |
| n06 | noisy | Pichle hafte ki total bikri batao | typed |  | correct |

## How this was measured

Speech = Prisma transcript at least 80% like the spoken question (recorded files only). Query = intent, metric, period and product all right. Answer = the figures equal those computed directly from the raw CSV files. Questions without a recording are tested as typed text.
