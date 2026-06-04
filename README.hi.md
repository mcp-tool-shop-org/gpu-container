<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.md">English</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<div align="center">

<img src="https://raw.githubusercontent.com/mcp-tool-shop-org/gpu-container/main/assets/logo.png" width="400" alt="gpu-container" />

![सीआई](https://github.com/mcp-tool-shop-org/gpu-container/actions/workflows/ci.yml/badge.svg)
![पाइपीआई](https://img.shields.io/pypi/v/gpu-container)
![एनपीएम](https://img.shields.io/npm/v/gpu-container)
![लाइसेंस: एमआईटी](https://img.shields.io/badge/License-MIT-blue.svg)
![हैंडबुक](https://img.shields.io/badge/handbook-docs-blue)

**एक जीपीयू-सक्षम कंटेनर डिवाइस को उजागर करता है। एक मॉडल-जागरूक रनटाइम यह तय करता है कि वीआरएएम, पिन की गई रैम और एनवीएमई में क्या होगा।**

</div>

अपने मशीन द्वारा समर्थित सबसे बड़े उपयोगी स्थानीय मॉडल को स्पष्ट प्लेसमेंट योजनाओं, बेंचमार्क परिणामों और अस्वीकृति के साथ चलाएं, जब योजना विफल हो जाएगी।

## आर्किटेक्चर

```
Windows / WSL2 / Linux host
  └─ GPU-enabled Docker container
      └─ Inference runtime
          ├─ VRAM: hot weights, active layers, activations, KV working set
          ├─ pinned RAM: CPU-offloaded weights, MoE experts, KV spill/reuse
          └─ NVMe: mmap shards, disk offload, cold experts, cold KV
```

## उत्पाद सीमा

```
Docker         = packaging + GPU exposure
CUDA/runtime   = compute backend
Planner        = memory law
Inference engine = execution
```

## मुख्य विशेषताएं

1. **हार्डवेयर प्रोफाइलर** — वीआरएएम, रैम, जीपीयू प्रकार, डब्ल्यूएसएल/देशी लिनक्स, एनवीएमई गति, क्यूडीए उपलब्धता का पता लगाएं
2. **मॉडल प्रोफाइलर** — घने बनाम एमओई, सबसे बड़ी परत, कुल वजन, क्वांटाइजेशन, संदर्भ लंबाई द्वारा केवी वृद्धि का पता लगाएं
3. **रनटाइम प्लानर** — लामा.cpp, vLLM, एक्सेलेरेट, टेंसरआरटी-एलएलएम, या डीपस्पीड-शैली ऑफलोड के लिए लॉन्च योजनाएं उत्पन्न करें
4. **प्लेसमेंट रसीद** — दिखाएं कि वीआरएएम में क्या है, रैम में क्या है, डिस्क पर क्या है, अपेक्षित बाधा, मापा गया टोकन/सेकंड
5. **एमओई-विशिष्ट पथ** — हमेशा सक्रिय परतों को जीपीयू पर रखें, विशेषज्ञों को सीपीयू/रैम, ठंडे फॉलबैक के लिए एनवीएमई पर रूट करें
6. **राउटिंग जोखिम कम करना** — मापें कि क्या किसी मॉडल का एमओई राउटिंग इतना तिरछा है कि प्रति-विशेषज्ञ कैश मदद करेगा, इससे पहले कि इसके लिए बनाया जाए (`gpu-container-concentration`)
7. **रिग-सुरक्षा वॉचडॉग** — कॉन्फ़िगर करने योग्य थ्रेसहोल्ड के विरुद्ध जीपीयू पावर/तापमान/वीआरएएम + होस्ट मेमोरी को पोल करें; एक एआई एजेंट या एक स्वायत्त लूप एक रन को तब तक रोक देता है जब तक कि यह मशीन को खतरे में न डाल दे (`gpu-container-watchdog`)

## मुख्य बाधा

विंडोज/डब्ल्यूएसएल पर, क्यूडीए एकीकृत मेमोरी ओवरसब्सक्रिप्शन सही तरीका नहीं है। क्यूडीए विंडोज/डब्ल्यूएसएल को सीमित एकीकृत-मेमोरी समर्थन के रूप में मानता है - कोई बारीक जीपीयू पेज-फॉल्ट माइग्रेशन नहीं, भौतिक वीआरएएम से परे कोई जीपीयू-मेमोरी ओवरसब्सक्रिप्शन नहीं। यह उत्पाद **स्पष्ट अनुमान मेमोरी प्लेसमेंट** है, न कि "डॉकर वीआरएएम ओवरफ्लो"।

## स्थिति

आज निर्मित और काम कर रहा है: `gpu-container-profile`, `gpu-container-plan`, `gpu-container-receipt` (पुनः अंशांकन लूप के साथ), `gpu-container-concentration` (राउटिंग जोखिम कम करना), और `gpu-container-watchdog` (सुरक्षित रूप से एक जीपीयू नौकरी की निगरानी करें)। लामा.cpp एकीकृत बैकएंड है; प्लेसमेंट गणित बैकएंड-अज्ञेयवादी है। [क्विकस्टार्ट](docs/quickstart.md) से शुरुआत करें।

## गोपनीयता और सुरक्षा

`gpu-container` एक **स्थानीय, ऑफ़लाइन उपकरण** है - यह कोई नेटवर्क कॉल नहीं करता है और डिफ़ॉल्ट रूप से या अन्यथा कोई टेलीमेट्री एकत्र नहीं करता है। यह जीपीयू मेट्रिक्स (`nvidia-smi` / NVML) और होस्ट मेमोरी (`psutil`), आपके द्वारा आपूर्ति किए गए मॉडल `config.json`, और आपके द्वारा इंगित किए गए JSON फ़ाइलों को पढ़ता है; यह केवल आपके द्वारा निर्दिष्ट आउटपुट पथों पर लिखता है। यह मॉडल वजन, क्रेडेंशियल्स या टोकन को नहीं पढ़ता या प्रसारित नहीं करता है। होस्ट-स्तरीय क्रियाएं (`wsl --shutdown`, `docker stop`, `kill`) केवल तभी चलती हैं जब आप वॉचडॉग के `--on-breach` के माध्यम से स्पष्ट रूप से ऑप्ट इन करते हैं; डिफ़ॉल्ट कभी भी उस नौकरी से परे आपकी मशीन को नहीं छूते जिसकी वे निगरानी करते हैं। पूर्ण नीति: [SECURITY.md](SECURITY.md)।

## प्रलेखन

- [`docs/quickstart.md`](docs/quickstart.md) — एंड-टू-एंड वॉकथ्रू: प्रोफाइल → योजना → वॉचडॉग के तहत लॉन्च → रसीद → पुन: अंशांकन
- [`docs/cli.md`](docs/cli.md) — पांच कमांड: सारांश, ध्वज, निकास कोड, उदाहरण
- [`docs/architecture.md`](docs/architecture.md) — मेमोरी-स्तरीय मॉडल, डेटा प्रवाह, एमओई विशेषज्ञ राउटिंग, पुन: अंशांकन लूप
- [`docs/features.md`](docs/features.md) — सात मुख्य विशेषताएं गहराई से
- [`docs/moe-lane-architecture.md`](docs/moe-lane-architecture.md) — प्रमुख एमओई लेन गहराई से
- [`docs/derisk-concentration.md`](docs/derisk-concentration.md) — प्रति-विशेषज्ञ-कैश जोखिम कम करने वाला गेट (राउटिंग एकाग्रता)
- [`docs/decisions/0001-per-expert-cache-build-vs-upstream.md`](docs/decisions/0001-per-expert-cache-build-vs-upstream.md) — एडीआर-0001: कैश तंत्र का उपयोग करें, नीति में योगदान करें
- [`docs/constraints.md`](docs/constraints.md) — गैर-लक्ष्य + विंडोज/डब्ल्यूएसएल क्यूडीए एकीकृत-मेमोरी सुधार
- [`docs/prior-art.md`](docs/prior-art.md) — रनटाइम जिन्हें हम व्यवस्थित करते हैं, और यह उत्पाद जो अंतर भरता है
- [`docs/feasibility.md`](docs/feasibility.md) — व्यवहार्यता मूल्यांकन, अनुसंधान आधार, और जो लाइव पुष्टि की गई है

---

<div align="center">

द्वारा निर्मित <a href="https://mcp-tool-shop.github.io/">एमसीपी टूल शॉप</a> · एमआईटी लाइसेंस प्राप्त

</div>
