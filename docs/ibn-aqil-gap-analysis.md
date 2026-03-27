# Gap Analysis: شرح ابن عقيل vs. Existing Grammar Files

**Date**: 2026-03-24
**Method**: Word-by-word study of all 62 syntactic chapters (lines 17-2194) of شرح ابن عقيل على ألفية ابن مالك, compared against the 6 grammar files (~3,000 lines).

## Executive Summary

| Metric | Value |
|--------|-------|
| Chapters studied | 62 (of 76; remaining 14 are صرف) |
| Total rules extracted | ~500+ |
| Rules covered in grammar files | ~125-150 (~25-30%) |
| Rules missing | ~350-375 (~70-75%) |
| Chapters entirely missing | 7 |
| Chapters with major gaps | 20+ |

The grammar files have an excellent **structural foundation** — the core topics, main rules, and decision trees are sound. But roughly **70-75% of the sub-rules, conditions, exceptions, خلاف, and edge cases** from Ibn Aqil are absent.

---

## I. CHAPTERS ENTIRELY MISSING (no content in any grammar file)

### Priority: HIGH (needed for correct i'rab decisions)

| # | Chapter | Key rules needed for i'rab |
|---|---------|---------------------------|
| 1 | **الاشتغال** (ch.18) | 5 cases: وجوب النصب (after شرط/تحضيض/عرض), وجوب الرفع (after إذا الفجائية), ترجيح النصب, ترجيح الرفع, الجواز |
| 2 | **التنازع** (ch.20) | البصريون: إعمال الثاني; الكوفيون: إعمال الأول; إضمار rules for the non-working verb |
| 3 | **الاستغاثة** (ch.47) | يا + لام مفتوحة + المستغاث + لام مكسورة + المستغاث له; عطف rules; ألف بدل اللام |
| 4 | **الندبة** (ch.48) | وا + المندوب + ألف + هاء السكت; ما لا يُندب (نكرة/مبهم/موصول بلا شهرة); حركة ما قبل ألف الندبة |
| 5 | **الترخيم** (ch.49) | حذف آخر المنادى; شروطه; لغتان (الانتظار / عدم الانتظار); حذف ما قبل الآخر conditions |
| 6 | **أسماء لازمت النداء** (ch.46) | فل, لؤمان, نومان; فَعالِ مقيس للسبّ والأمر; فُعَلُ للسبّ |
| 7 | **المنادى المضاف لياء المتكلم** (ch.45) | 5 أوجه; يا أبتِ/أمتِ; ابن أم/ابن عم |

### Priority: LOW (pedagogical / rare)

| # | Chapter | Notes |
|---|---------|-------|
| 8 | **الإخبار بالذي وأل** (ch.59) | Grammatical exercise, not practical i'rab |
| 9 | **الحكاية** (ch.62) | حكاية بأيّ/بمَن, mostly for interrogative contexts |

---

## II. CHAPTERS WITH MAJOR GAPS (core rules exist but 60-80% of sub-rules missing)

### A. النواسخ (grammar-rules.md)

**كان وأخواتها** — 39 rules found, ~29 missing:
- حذف النافي مع أفعال الاستمرار بعد القسم only (تالله تفتأ)
- فتئ وزال (يزال) لا تأتيان تامتين
- عمل اسم الفاعل والمصدر من كان (كائن، كون)
- كان الزائدة: مواضع القياس (بين ما وفعل التعجب) vs السماع
- حذف كان بعد إن/لو + تعويض "ما" (أما أنت برّاً فاقترب)
- حذف نون يكن المجزومة (لم يك) — conditions
- ضمير الشأن بعد كان
- منع تقديم خبر ما زال/ليس/دام على الناسخ أو "ما"
- زيادة الباء في خبر ليس/ما (تفصيل)

**إنّ وأخواتها** — 40 rules, ~28 missing:
- 6 مواضع وجوب الكسر (only 2 documented): صدر صلة, جواب قسم + لام, حالية, تعليق
- 4 مواضع جواز الفتح والكسر
- اللام المزحلقة: 8+ sub-rules (ما تدخل عليه / ما لا تدخل: لا على منفي, لا على ماضٍ متصرف بلا قد, تدخل على معمول الخبر المتوسط, على ضمير الفصل)
- أحكام العطف على اسم إنّ (before/after الخبر)
- المخففة من الثقيلة: الفواصل (قد/سوف/السين/النفي/لو), إعمال إنْ المخففة (قليل)

**لا النافية للجنس** — 28 rules, ~23 missing:
- 5 أوجه عند تكرار لا مع العطف
- 3 أوجه لنعت اسم لا المبني (بناء/نصب/رفع)
- العطف بمعرفة: رفع only
- همزة الاستفهام + لا

**ظنّ وأخواتها** — 32 rules, ~26 missing:
- حجا missing from list
- وهب (= صيّرني) وردّ missing from أفعال التحويل
- كل أدوات التعليق الستة: ما، إن، لا النافيات + لام الابتداء + لام القسم + الاستفهام
- الإلغاء: توسط = سيّان; تأخر = الإلغاء أحسن; تقدم = ممتنع عند البصريين
- إجراء القول مجرى الظنّ (4 شروط عند عامة العرب)
- علم بمعنى عرف = مفعول واحد; رأى الحلمية = مفعولان

**كاد وأخواتها** — 26 rules, ~18 missing:
- **كرب** و**علق** missing entirely from the verb list
- تصرف كاد وأوشك (مضارع + اسم فاعل)
- ندرة مجيء الخبر اسماً (عسيت صائماً)
- لغة تميم vs الحجاز في عسى المسبوقة باسم

### B. الفاعل والمفاعيل (roles-and-functions.md, sentence-analysis.md)

**الفاعل** — massive agreement gaps:
- تاء التأنيث: obligatory (ضمير مؤنث / فاعل حقيقي ظاهر) vs optional (مجازي / فصل بغير إلا / جمع تكسير) vs preferred-omission (فصل بإلا)
- لغة أكلوني البراغيث (verb agrees with ظاهر dual/plural)
- وجوب تقديم المفعول (شرط, استفهام, إياك نعبد)
- وجوب تقديم الفاعل عند اللبس (ضرب موسى عيسى)
- الحصر بإلا وإنما: المحصور يؤخر

**الحال** — many sub-rules missing:
- 9 cases for جمود الحال (سعر/تفاعل/تشبيه...)
- مسوغات الحال من نكرة
- الحال from مضاف إليه (3 conditions)
- المضارع المثبت لا يقترن بالواو as حال
- Cases of وجوب حذف العامل

**المفعول المطلق** — 7 cases of وجوب حذف العامل, only 1 covered

**الاستثناء** — missing:
- تقديم المستثنى على المستثنى منه
- تكرار إلا (للتوكيد / لغير التوكيد)
- ليس/لا يكون as exception tools
- المفرغ لا يقع في كلام موجب

### C. حروف الجر والإضافة (grammar-rules.md, roles-and-functions.md)

**حروف الجر** — highest-impact gap:
- الباء: 11 meanings, only 5 documented (missing: تعدية, تعويض, مصاحبة, بمعنى مِن, بمعنى عن, بدل)
- اللام: 6 meanings, only 2 documented (missing: شبه الملك, تعدية, انتهاء, زائدة)
- مِن: 6 meanings, 4 documented (missing: بدل, ابتداء الغاية الزمانية)
- مذ/منذ dual nature (حرف جر vs اسم)
- ربّ: حذف after واو/فاء/بل; restriction to نكرة
- حتى: only governs آخر or متصل بالآخر
- ما الزائدة: كافة (after ربّ/الكاف) vs غير كافة (after مِن/عن/الباء)

**الإضافة** — major gaps:
- تقدير meaning (3 types: اللام / مِن / في)
- غير/قبل/بعد 4 states (مضافة / حُذف+نُوي لفظه / حُذف+لم يُنوَ / حُذف+نُوي معناه → مبنية على الضم)
- حذف المضاف (المضاف إليه يأخذ إعرابه)
- الفصل بين المضاف والمضاف إليه (conditions)

### D. إعراب الفعل والشرط (grammar-rules.md)

**إعراب الفعل**:
- شروط إذن الناصبة (3 conditions + exceptions)
- أنْ بعد يقين/ظن (tripartite rule)
- حتى + حال = رفع واجب (حتى الابتدائية)
- الطلب المحض restriction (اسم فعل → لا نصب بالفاء)

**عوامل الجزم**:
- إذما missing from أدوات الشرط الجازمة
- لم vs لما distinction (لما = متصل بالحال)
- 4 tense combinations for شرط/جزاء
- فعل مضارع بعد الجزاء مع فاء/واو (3 إعراب options)
- حذف جواب الشرط / حذف فعل الشرط
- اجتماع الشرط والقسم — ذو خبر exception

**لو**:
- لو المصدرية (= أنْ) — not documented
- جواب لو forms (مثبت باللام, منفي بلم بلا لام, منفي بما)
- لو + أنّ analysis

**أمّا**:
- = مهما يك من شيء; لزوم الفاء; حذف الفاء rules

**لولا/لوما**:
- التحضيض usage completely missing

### E. التوابع والأساليب (sentence-analysis.md, asaleeb.md)

**النعت** — missing:
- 4-from-10 matching (حقيقي) vs 2-from-5 (سببي)
- ما ينعت به (مشتق + 4 مؤول)
- الجملة الطلبية ممنوعة
- النعت بالمصدر; تكرر النعوت; القطع

**التوكيد** — missing:
- عامة as additional word; توكيد النكرة (بصري vs كوفي)
- فصل rules for ضمير متصل مرفوع
- التوكيد اللفظي for ضمائر/حروف

**عطف النسق** — missing:
- Most particle details (أم متصلة/منقطعة, حتى conditions, إما ليست عاطفة, بل)
- العطف على ضمير رفع متصل (فصل rules)
- العطف على ضمير جر (خلاف)

**البدل** — missing: بدل مباين (إضراب/غلط), بدل الفعل من الفعل

**النداء** — missing: حذف حرف النداء conditions, تابع المنادى rules

**الصفة المشبهة** — missing:
- Diagnostic test (يُستحسن جرّ فاعلها بها)
- Only from لازم, only for الحال
- Key difference from اسم الفاعل: لا تقديم, only سببي

**ما لا ينصرف** — missing:
- Many subcases of العلل التسع (وصفية+ألف ونون شرط عدم التاء, عارض الوصفية/الاسمية, العلمية+التأنيث بالتعليق 5 subcases, العلمية+العجمة شرط العلمية في اللسان الأعجمي)

### F. المبتدأ والخبر (roles-and-functions.md)

- الوصف المبتدأ (أقائمٌ الزيدان) — conditions and 3 paradigms
- 12+ additional مسوغات الابتداء بالنكرة
- 4 types of رابط for خبر الجملة
- وجوب حذف المبتدأ (4 cases)
- تعدد الخبر بلا عطف

### G. الأساسيات (not in any file)

- العلم: اسم/كنية/لقب, مرتجل/منقول, مركب مزجي/إضافي
- أسماء الإشارة: 7 feminine forms, 3-tier distance, هنا/هناك/ثمّ
- الموصول: full paradigms, حذف العائد rules (4 sub-systems), أيّ الموصولة, ذا الموصولة
- أل: أل الزائدة, أل اللمحية, أل الغلبة

---

## III. WHAT'S WELL-COVERED (no major gaps)

These topics are adequately covered in the grammar files:
- الأسماء الخمسة (special-cases.md) — شروط + جدول تشخيصي
- الأفعال الخمسة (special-cases.md) — صيغ + علامات
- المثنى / جمع المذكر السالم / جمع المؤنث السالم (special-cases.md)
- الإعراب التقديري (special-cases.md) — 3 فئات
- الإعراب المحلي (special-cases.md) — 7 categories
- بناء الأفعال التفصيلي (special-cases.md)
- الضمائر (special-cases.md) — جداول كاملة
- المصدر المؤول (grammar-rules.md) — حروف مصدرية + إعراب
- Particle disambiguation trees (disambiguation.md) — ما/لا/أن/إن/الواو/الفاء/من/الباء/اللام/أل/أنّ-إنّ/جعل
- المرفوعات / المنصوبات / المجرورات lists (roles-and-functions.md)
- تعلّق شبه الجملة (roles-and-functions.md)
- الجمل التي لها محل / ليس لها محل (sentence-analysis.md)
- أسلوب القسم (asaleeb.md) — أركان + أدوات + جواب
- الاختصاص (asaleeb.md)
- التحذير والإغراء (asaleeb.md)
- أسماء الأفعال (asaleeb.md) — basic coverage
- العدد والمعدود (special-cases.md) — basic table
- كم الاستفهامية/الخبرية (asaleeb.md)

---

## IV. RECOMMENDED ACTION PLAN

### Phase 1: Critical additions (highest i'rab impact)

1. **Add الاشتغال section** to asaleeb.md (5 cases)
2. **Add التنازع section** to asaleeb.md (already listed but needs content)
3. **Expand حروف الجر** meanings in grammar-rules.md (especially الباء 11 meanings, اللام 6)
4. **Add تاء التأنيث agreement rules** to a new section (obligatory/optional/preferred-omission)
5. **Add تقديم/تأخير الفاعل والمفعول** rules
6. **Expand إنّ وأخواتها** with كسر/فتح rules, اللام المزحلقة details
7. **Expand أدوات الشرط** — add إذما, 4 tense combinations, حذف الجواب
8. **Add لو section** — المصدرية, الشرطية, جواب لو forms
9. **Add أمّا section** — لزوم الفاء, ما يجوز بين أمّا والفاء
10. **Expand لولا/لوما** — add التحضيض usage

### Phase 2: Important additions (affect edge cases)

11. **Add كاد missing verbs**: كرب, علق
12. **Add ظنّ missing verbs**: حجا, وهب (تحويل), ردّ
13. **Expand التعليق**: all 6 particles; الإلغاء conditions (توسط/تأخر/تقدم)
14. **Add الاستغاثة section** to sentence-analysis.md or asaleeb.md
15. **Add الندبة section**
16. **Add الترخيم section**
17. **Expand النعت**: 4-from-10 rule, القطع, الطلبية, المصدر
18. **Expand عطف النسق**: أم متصلة/منقطعة, العطف على ضمير rules
19. **Expand الإضافة**: تقدير (اللام/من/في), 4 states of غير/قبل/بعد
20. **Add الصفة المشبهة** detailed rules (diagnostic, restrictions vs اسم الفاعل)

### Phase 3: Completeness (less common but documented)

21. Add الموصول full paradigms + حذف العائد rules
22. Add أسماء الإشارة full forms + distance system
23. Add العلم rules (اسم/كنية/لقب, مركب مزجي)
24. Expand مسوغات الابتداء بالنكرة (12+ additional)
25. Expand ما لا ينصرف subcases
26. Add المفعول المطلق وجوب حذف العامل (7 cases)
27. Add كأيّ/كذا to كم section
28. Add إذن conditions (3 شروط)
29. Expand الحال (جمود conditions, مسوغات من نكرة)
30. Add أسماء لازمت النداء
