# I'rab Skill — Full Architecture

## 1. System Overview

```mermaid
flowchart TD
    USER["**User Input**<br/>أعرب: كتبَ الطالبُ الرسالةَ"]
    TRIGGER["**SKILL.md** (356 lines)<br/>Detects trigger · Activates 4-pass pipeline"]

    MCP["**MCP Server**<br/>arabic-morphology<br/>Buckwalter DB<br/>82,158 stems"]
    REFS["**Reference Files**<br/>6 files · 3,003 lines<br/>Complete Arabic grammar"]
    EXAMPLES["**Examples**<br/>25 worked examples<br/>759 lines"]

    P1["**Pass 1: التصنيف**<br/>Classify every word<br/>→ Classification Table"]
    P2["**Pass 2: العوامل**<br/>Map governors<br/>→ Governor Map"]
    P3["**Pass 3: الإعراب**<br/>Full structured analysis<br/>→ Per-word i'rab"]
    P4["**Pass 4: المراجعة**<br/>6-point verification<br/>→ Checklist ✓/✗"]

    OUTPUT["**Final Output**<br/>4 visible passes<br/>Structured · Verified"]

    USER --> TRIGGER
    TRIGGER --> P1
    MCP -.->|"definitive POS,<br/>gender, number"| P1
    REFS -.->|"disambiguation<br/>decision trees"| P1
    P1 --> P2
    MCP -.->|"transitivity<br/>لازم/متعدٍّ"| P2
    REFS -.->|"عامل→أثر<br/>mappings"| P2
    P2 --> P3
    REFS -.->|"case signs,<br/>special cases"| P3
    EXAMPLES -.->|"pattern<br/>reference"| P3
    P3 --> P4
    P4 -->|"✓ all checks pass"| OUTPUT
    P4 -->|"✗ fix errors"| P3

    style USER fill:#1a1a2e,stroke:#e94560,color:#fff
    style TRIGGER fill:#16213e,stroke:#0f3460,color:#fff
    style MCP fill:#0f3460,stroke:#e94560,color:#fff
    style REFS fill:#0f3460,stroke:#53a8b6,color:#fff
    style EXAMPLES fill:#0f3460,stroke:#53a8b6,color:#fff
    style P1 fill:#1a1a2e,stroke:#53a8b6,color:#fff
    style P2 fill:#1a1a2e,stroke:#53a8b6,color:#fff
    style P3 fill:#1a1a2e,stroke:#53a8b6,color:#fff
    style P4 fill:#1a1a2e,stroke:#e94560,color:#fff
    style OUTPUT fill:#16213e,stroke:#53a8b6,color:#fff
```

## 2. The 4-Pass Pipeline

```mermaid
flowchart LR
    subgraph PASS1["**Pass 1: التصنيف**"]
        direction TB
        IN1["Raw Arabic text"]
        T1["MCP analyze_sentence()"]
        T2["disambiguation.md<br/>particle decision trees"]
        OUT1["Classification Table<br/>word · type · subtype<br/>gender · number · مبني/معرب"]
        IN1 --> T1 --> OUT1
        IN1 --> T2 --> OUT1
    end

    subgraph PASS2["**Pass 2: العوامل**"]
        direction TB
        IN2["Classification Table"]
        T3["MCP check_transitivity()"]
        T4["grammar-rules.md<br/>roles-and-functions.md"]
        OUT2["Governor Map<br/>word · عامل · expected case<br/>+ hidden elements<br/>+ embedded clauses"]
        IN2 --> T3 --> OUT2
        IN2 --> T4 --> OUT2
    end

    subgraph PASS3["**Pass 3: الإعراب**"]
        direction TB
        IN3["Pass 1 + Pass 2"]
        T5["special-cases.md<br/>Case Signs Table"]
        OUT3["Structured Analysis<br/>ALL fields per word:<br/>type · role · case · sign<br/>sign_type · governor · محل"]
        IN3 --> T5 --> OUT3
    end

    subgraph PASS4["**Pass 4: المراجعة**"]
        direction TB
        IN4["Full Analysis"]
        CHK["6 Verification Checks"]
        OUT4["✓ Verified Output"]
        IN4 --> CHK --> OUT4
    end

    PASS1 ==> PASS2 ==> PASS3 ==> PASS4

    style PASS1 fill:#1a1a2e,stroke:#53a8b6,color:#fff
    style PASS2 fill:#1a1a2e,stroke:#53a8b6,color:#fff
    style PASS3 fill:#1a1a2e,stroke:#53a8b6,color:#fff
    style PASS4 fill:#1a1a2e,stroke:#e94560,color:#fff
```

## 3. MCP Server — Deterministic Morphology

```mermaid
flowchart LR
    subgraph CLAUDE["**Claude Code (LLM)**<br/>نحو — Syntactic Reasoning"]
        C1["Pass 1: calls analyze_sentence()"]
        C2["Pass 2: calls check_transitivity()"]
        C3["Ad hoc: calls analyze_word()"]
    end

    subgraph MCP["**MCP Server: arabic-morphology**<br/>صرف — Deterministic Lookup"]
        direction TB
        subgraph TOOLS["Exposed Tools"]
            T1["**analyze_word**(word)<br/>→ all readings: vocalized,<br/>POS, gender, number,<br/>definiteness, gloss"]
            T2["**analyze_sentence**(text)<br/>→ per-word analysis<br/>(top 5 readings each)"]
            T3["**check_transitivity**(verb)<br/>→ form (I-X), voice,<br/>لازم/متعدٍّ"]
        end
        subgraph DB["Buckwalter Database"]
            D1["299 prefixes"]
            D2["82,158 stems<br/>38,600 lemmas"]
            D3["618 suffixes"]
        end
        TOOLS --> DB
    end

    C1 -->|stdio| T2
    C2 -->|stdio| T3
    C3 -->|stdio| T1

    style CLAUDE fill:#16213e,stroke:#e94560,color:#fff
    style MCP fill:#0f3460,stroke:#53a8b6,color:#fff
    style TOOLS fill:#1a1a2e,stroke:#53a8b6,color:#fff
    style DB fill:#1a1a2e,stroke:#e94560,color:#fff
```

## 4. Reference Files — Loaded on Demand

```mermaid
flowchart TD
    SKILL["**SKILL.md** (always loaded)<br/>Pipeline · Case Signs Table<br/>Error Prevention Rules · MCP integration"]

    GR["**grammar-rules.md** (719 lines)<br/>كان · إنّ · ظنّ · أعطى · أرى<br/>كاد · ما الحجازية · المبني للمجهول<br/>الشرط · النصب · الجزم · لا النافية للجنس<br/>المصدر المؤول · المشتقات · نون التوكيد"]

    SC["**special-cases.md** (519 lines)<br/>الأسماء الخمسة · الأفعال الخمسة<br/>الممنوع من الصرف · التقديري · المحلي<br/>بناء الأفعال · الضمائر · العدد والمعدود"]

    RF["**roles-and-functions.md** (425 lines)<br/>المفعول المطلق · لأجله · فيه · معه<br/>نزع الخافض · المضاف إليه<br/>تعلّق شبه الجملة · مسوغات الابتداء"]

    SA["**sentence-analysis.md** (334 lines)<br/>التوابع: نعت · عطف · توكيد · بدل<br/>الحال · التمييز · الاستثناء · النداء<br/>٧ جمل لها محل · ٧ جمل لا محل"]

    AS["**asaleeb.md** (450 lines)<br/>التعجب · المدح/الذم · التفضيل<br/>القسم · الاشتغال · التنازع<br/>الاختصاص · الإغراء/التحذير<br/>أسماء الأفعال · لا سيّما · كم"]

    DIS["**disambiguation.md** (556 lines)<br/>ALWAYS LOADED<br/>11 particle decision trees<br/>Transitivity heuristics<br/>Undiacritized text rules<br/>Scope resolution"]

    EX["**examples.md** (759 lines)<br/>25 worked examples"]

    SKILL --> |"كان/إنّ/ظنّ/كاد<br/>شرط/نصب/جزم..."| GR
    SKILL --> |"أسماء٥/أفعال٥<br/>ممنوع/تقديري/عدد"| SC
    SKILL --> |"مفاعيل/إضافة<br/>تعلّق/مسوغات"| RF
    SKILL --> |"توابع/حال/تمييز<br/>جمل مضمّنة"| SA
    SKILL --> |"تعجب/مدح/تفضيل<br/>قسم/اشتغال..."| AS
    SKILL --> |always| DIS
    SKILL -.-> EX

    style SKILL fill:#e94560,stroke:#fff,color:#fff
    style DIS fill:#e94560,stroke:#fff,color:#fff
    style GR fill:#0f3460,stroke:#53a8b6,color:#fff
    style SC fill:#0f3460,stroke:#53a8b6,color:#fff
    style RF fill:#0f3460,stroke:#53a8b6,color:#fff
    style SA fill:#0f3460,stroke:#53a8b6,color:#fff
    style AS fill:#0f3460,stroke:#53a8b6,color:#fff
    style EX fill:#16213e,stroke:#53a8b6,color:#fff
```

## 5. The Core Split: صرف vs نحو

```mermaid
flowchart LR
    subgraph SARF["**صرف (Morphology)**<br/>DETERMINISTIC — Code"]
        direction TB
        S1["What IS this word?"]
        S2["Root: ك ت ب"]
        S3["Pattern: فَعَلَ (Form I)"]
        S4["POS: verb, perfect, active"]
        S5["Transitive: yes"]
        S6["Gender: masc, Number: sing"]
        S1 --> S2 --> S3 --> S4 --> S5 --> S6
    end

    subgraph NAHW["**نحو (Syntax)**<br/>REASONING — LLM"]
        direction TB
        N1["What ROLE does it play?"]
        N2["Sentence type: فعلية"]
        N3["Governor: الابتداء/الفعل/إنّ..."]
        N4["Role: فاعل → مرفوع"]
        N5["Sign: الضمة (مفرد صحيح)"]
        N6["Verify: عامل↔حالة↔علامة ✓"]
        N1 --> N2 --> N3 --> N4 --> N5 --> N6
    end

    INPUT["Arabic Word"] --> SARF
    SARF ==>|"structured<br/>morphological data"| NAHW
    NAHW ==> RESULT["Complete I'rab"]

    style SARF fill:#0f3460,stroke:#e94560,color:#fff
    style NAHW fill:#16213e,stroke:#53a8b6,color:#fff
    style INPUT fill:#1a1a2e,stroke:#fff,color:#fff
    style RESULT fill:#1a1a2e,stroke:#53a8b6,color:#fff
```

## 6. File Inventory

| File | Lines | Contents |
|------|------:|---------|
| `SKILL.md` | 356 | Main skill: 4-pass pipeline, case signs table, error prevention, MCP integration |
| `references/grammar-rules.md` | 719 | النواسخ, الحروف العاملة, المبني للمجهول, المشتقات, المصدر المؤول |
| `references/disambiguation.md` | 556 | 11 particle decision trees, transitivity, tashkeel disambiguation, scope |
| `references/special-cases.md` | 519 | العلامات الفرعية, بناء الأفعال, الضمائر, العدد والمعدود |
| `references/asaleeb.md` | 450 | 12 أساليب نحوية (تعجب, مدح, تفضيل, قسم, ...) |
| `references/roles-and-functions.md` | 425 | المفاعيل الخمسة, المضاف إليه, تعلّق شبه الجملة, مسوغات |
| `references/sentence-analysis.md` | 334 | التوابع, الحال, التمييز, 7+7 جمل لها/ليس لها محل |
| `examples/examples.md` | 759 | 25 fully-worked canonical examples |
| `mcp-server/server.py` | 336 | MCP server wrapping Buckwalter (82,158 stems) |
| **Total** | **4,454** | |
