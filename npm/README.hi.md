<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.md">English</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

[![सीआई](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml)
[![पाइपीआई](https://img.shields.io/pypi/v/gpu-container)](https://pypi.org/project/gpu-container/)
[![एनपीएम](https://img.shields.io/npm/v/gpu-container)](https://www.npmjs.com/package/gpu-container)
[![लाइसेंस: एमआईटी](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/LICENSE)
[![हैंडबुक](https://img.shields.io/badge/handbook-docs-blue)](https://mcp-tool-shop-org.github.io/gpu-container/)

**एक जीपीयू-सक्षम कंटेनर डिवाइस को उजागर करता है। एक मॉडल-जागरूक रनटाइम यह तय करता है कि वीआरएएम, पिन की गई रैम और एनवीएमई में क्या होगा।**

</div

अपने मशीन द्वारा समर्थित सबसे बड़े उपयोगी स्थानीय मॉडल को चलाएं - स्पष्ट प्लेसमेंट योजनाओं, बेंचमार्क परिणामों और उस स्थिति में इनकार के साथ जब योजना विफल हो जाए। यह एनपीएम पैकेज एक **शून्य-आवश्यकता वाला लॉन्चर** है: `npx gpu-container` प्लेटफ़ॉर्म बाइनरी को [गिटहब रिलीज़](https://github.com/mcp-tool-shop-org/gpu-container/releases) से डाउनलोड करता है, प्रकाशित चेकसम के विरुद्ध इसके SHA256 को सत्यापित करता है, इसे कैश करता है, और इसे चलाता है। **पायथन की आवश्यकता नहीं है।**

```bash
npx gpu-container --help
npx gpu-container plan --profile profile.json --model-config qwen3.json --quant gguf-q4_k_m
```

> क्या आप पायथन पसंद करते हैं? `pip install "gpu-container[host]"` सीधे पांच `gpu-container-*` कमांड स्थापित करता है।

## यह क्यों मौजूद है

विंडोज/डब्ल्यूएसएल2 पर, क्यूडीए यूनिफाइड-मेमोरी ओवरसब्सक्रिप्शन **उपलब्ध नहीं** है (एनवीडिया द्वारा पुष्टि की गई) और लिनक्स पर भी डिकोड के लिए गलत उपकरण है। इसलिए `gpu-container` रनटाइम ओवरफ्लो जादू पर निर्भर नहीं करता है - यह **स्पष्ट, घोषित प्लेसमेंट** को उत्पाद बनाता है। यही इसकी ताकत है।

## यह क्या करता है

`gpu-container <कमांड>` एक बाइनरी में पांच उपकरण हैं:

| कमांड | यह करता है |
|---|---|
| `profile` | मशीन (वीआरएएम, पीसीआईई, एनवीएमई, पिन करने योग्य रैम, सीपीयू बैंडविड्थ) + मॉडल को मापता है |
| `plan` | स्पष्ट वीआरएएम/रैम/एनवीएमई प्लेसमेंट + एक कैलिब्रेटेड थ्रूपुट पूर्वानुमान की गणना करता है; **शिप या इनकार** |
| `receipt` | वास्तविक `llama-bench` रन के विरुद्ध एक योजना को सत्यापित करता है; एक कैलिब्रेशन बिंदु वापस लिखता है |
| `concentration` | प्रति-विशेषज्ञ कैश को जोखिम से बचाता है - इसके लिए निर्माण करने से पहले रूटिंग एकाग्रता को मापता है |
| `watchdog` | एक जीपीयू नौकरी की निगरानी करता है; होस्ट-मेमोरी / पावर / वीआरएएम उल्लंघन पर रद्द करता है |

- **एमओई विशेषज्ञ टियरिंग** (प्रमुख) - वीआरएएम में साझा/अटेंशन परतें, सीपीयू रैम में विशेषज्ञ `llama.cpp --n-cpu-moe` के माध्यम से। Qwen3-30B-A3B पर लाइव साबित।
- **मापे गए परिणाम** - एक वास्तविक रन छत *सीलिंग* और एक कैलिब्रेटेड *बैंड* के विरुद्ध पूर्वानुमान को सत्यापित करता है; परिणाम अगली योजना को बेहतर बनाता है।
- **ईमानदार इनकार** - क्या कोई योजना >1 टोकन/सेकंड से अधिक नहीं है? यह इनकार कर देता है, और बताता है कि क्यों।
- **मशीन-सुरक्षा वॉचडॉग** - एक वास्तविक घटना से उत्पन्न; किसी भी जीपीयू नौकरी की निगरानी करें ताकि एक खराब योजना मशीन को बंद न कर सके।

## सुरक्षित रूप से एक जीपीयू नौकरी चलाएं

```bash
gpu-container watchdog run --on-breach kill-job --peaks-out peaks.json -- \
  docker run --rm --gpus all -v "E:/AI-Models:/models" ghcr.io/ggml-org/llama.cpp:full-cuda \
    llama-bench -m /models/model.gguf --n-cpu-moe 0 -o json > bench.json
```

## दस्तावेज़

- **क्विकस्टार्ट + हैंडबुक:** https://mcp-tool-shop-org.github.io/gpu-container/handbook/
- **स्रोत + पूर्ण दस्तावेज़:** https://github.com/mcp-tool-shop-org/gpu-container
- **गोपनीयता और सुरक्षा:** स्थानीय, ऑफ़लाइन, कोई टेलीमेट्री नहीं, कोई नेटवर्क आउटगोइंग नहीं। [SECURITY.md](https://github.com/mcp-tool-shop-org/gpu-container/blob/main/SECURITY.md)

<div align="center">

<a href="https://mcp-tool-shop.github.io/">एमसीपी टूल शॉप</a> द्वारा निर्मित · एमआईटी लाइसेंस प्राप्त

</div
