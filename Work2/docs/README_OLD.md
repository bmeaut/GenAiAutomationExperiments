# Multi-Platform Office Integration Project

## 🎯 Projekt Áttekintés
**Interakció Google Sheets, Google Docs, Excel és Word, office makrók között**

Ez egy technológiai kísérleti projekt, amely arra keresi a választ, hogy hogyan lehet Excel makróból vagy Python scriptből könnyen elérni a fenti adatforrásokat, és azon között adatokat átvinni.

### 🔍 Fő Kutatási Kérdés
Hogyan lehet hatékonyan elérni az adatforrásokat:
- **Google Sheets** (Google Forms kimenetekből)
- **Google Docs** 
- **Excel fájlok**
- **Word dokumentumok**

És automatikusan adatokat átvinni közöttük?

### 🎪 Példa Használati Eset
**Automatizált Dokumentum Generálási Pipeline:**
1. **Google Forms** → Válaszok mentése **Google Sheets**-be
2. **Python Script** figyeli az új sorokat a Google Sheets-ben
3. **Word Sablon** + Sor Adatok → **PDF Dokumentum** generálása
4. **Email** PDF melléklettel, táblázat alapján megcímezve
5. **Küldésre kész** - felhasználónak feldobva végleges jóváhagyásra

## 📁 Projekt Struktúra
```
Work2/
├── README.md                     # Ez a fájl
├── requirements.txt              # Python függőségek
├── config/
│   ├── credentials.json          # Google API hitelesítő adatok
│   ├── settings.yaml            # Konfigurációs beállítások
│   └── email_templates.json     # Email sablonok
├── data/
│   ├── sample_sheets/           # Minta Google Sheets exportok
│   ├── sample_forms/            # Minta űrlap adatok
│   └── test_data/              # Teszt adathalmazok
├── templates/
│   ├── word_templates/          # Word dokumentum sablonok
│   ├── google_docs_templates/   # Google Docs sablonok
│   └── email_templates/         # Email üzenet sablonok
├── scripts/
│   ├── python/
│   │   ├── google_integration.py      # Google APIs integráció
│   │   ├── office_integration.py      # Office automatizálás
│   │   ├── pdf_generator.py          # PDF generálás
│   │   ├── email_automation.py       # Email kezelés
│   │   └── main_pipeline.py          # Fő automatizálási pipeline
│   ├── vba/
│   │   ├── excel_macros.bas          # Excel VBA makrók
│   │   └── word_macros.bas           # Word VBA makrók
│   └── powershell/
│       ├── office_automation.ps1     # PowerShell automatizálás
│       └── google_integration.ps1    # PowerShell Google APIs
├── output/
│   ├── generated_pdfs/          # Generált PDF fájlok
│   ├── generated_emails/        # Email tervezetek
│   └── logs/                   # Feldolgozási naplók
├── tests/
│   ├── test_google_integration.py
│   ├── test_office_integration.py
│   └── test_pipeline.py
└── docs/
    ├── setup_guide.md          # Beállítási útmutató
    ├── api_documentation.md    # API használati útmutató
    └── troubleshooting.md      # Gyakori problémák
```

## 🚀 Funkciók

### ✅ Megvalósítandó
- [ ] Google Sheets API integráció
- [ ] Google Docs API integráció  
- [ ] Excel fájl feldolgozás
- [ ] Word dokumentum automatizálás
- [ ] PDF generálás sablonokból
- [ ] Email automatizálás
- [ ] Multi-platform támogatás (Windows/Mac/Linux)

### 🔧 Használt Technológiák
- **Python**: Fő automatizálási nyelv
- **Google APIs**: Sheets, Docs, Gmail
- **python-docx**: Word dokumentum feldolgozás
- **openpyxl**: Excel fájl kezelés
- **ReportLab/WeasyPrint**: PDF generálás
- **smtplib/Gmail API**: Email küldés
- **VBA**: Excel/Word makrók
- **PowerShell**: Windows automatizálás

## 📋 Beállítási Útmutató

### 1. Python Függőségek
```bash
pip install -r requirements.txt
```

### 2. Google API Beállítás
1. Menj a [Google Cloud Console](https://console.cloud.google.com/)-ra
2. Hozz létre új projektet vagy válassz meglévőt
3. Engedélyezd az API-kat: Sheets, Docs, Gmail
4. Hozz létre hitelesítő adatokat (Service Account vagy OAuth2)
5. Töltsd le a `credentials.json`-t a `config/` mappába

### 3. Konfiguráció
Szerkeszd a `config/settings.yaml` fájlt a beállításaiddal:
```yaml
google:
  credentials_file: "config/credentials.json"
  sheets_id: "a_te_google_sheet_id_d"
  
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: "a_te_emailed@gmail.com"
  
templates:
  word_template_dir: "templates/word_templates"
  output_dir: "output/generated_pdfs"
```

## 🎮 Használati Példák

### Gyors Indítás
```bash
# Fő pipeline futtatása
python scripts/python/main_pipeline.py

# PDF generálás adott sorból
python scripts/python/pdf_generator.py --row-id 5

# Google Sheets kapcsolat tesztelése
python scripts/python/google_integration.py --test
```

### VBA Használat
Nyisd meg az Excel-t és futtasd:
```vba
Sub AutomateFromExcel()
    Call ProcessGoogleSheetsData
End Sub
```

## 📊 Minta Munkafolyamatok

### Munkafolyamat 1: Űrlap → PDF Pipeline
1. **Google Form** beküldés új sort hoz létre
2. **Python script** észleli az új sort
3. **Word sablon** kitöltése űrlap adatokkal
4. **PDF** generálás és mentés
5. **Email** tervezet létrehozása PDF melléklettel

### Munkafolyamat 2: Excel → Google Docs
1. **Excel makró** adatok olvasása
2. **Google Docs** sablon duplikálása
3. **Helyőrzők** cseréje Excel adatokra
4. **Dokumentum** megosztása érintettekkel

### Munkafolyamat 3: Tömeges Feldolgozás
1. **Google Sheets** több bejegyzéssel
2. **Batch feldolgozás** minden sorból
3. **Egyedi PDF-ek** minden bejegyzéshez
4. **Tömeges email** küldés személyre szabott mellékletekkel

## 🔗 API Integrációs Pontok

### Google APIs
- **Sheets API**: Táblázat adatok olvasása/írása
- **Docs API**: Dokumentumok létrehozása/módosítása  
- **Gmail API**: Email küldés mellékletekkel

### Office Integráció
- **COM Objects**: Közvetlen Office automatizálás
- **Fájl Feldolgozás**: Office fájlok olvasása/írása
- **Sablon Motor**: Dinamikus tartalom generálás

## 📈 Teljesítmény Megfontolások
- **Batch Feldolgozás**: Több bejegyzés hatékony kezelése
- **Rate Limiting**: API kvóták tiszteletben tartása
- **Hibakezelés**: Robusztus hiba helyreállítás
- **Naplózás**: Átfogó művelet követés

## 🛠️ Fejlesztés & Tesztelés
```bash
# Tesztek futtatása
python -m pytest tests/

# Debug mód
python scripts/python/main_pipeline.py --debug

# Sablonok validálása
python scripts/python/template_validator.py
```

## 📞 Támogatás & Hibaelhárítás
Nézd meg a `docs/troubleshooting.md` fájlt gyakori problémákért és megoldásokért.

---
**Létrehozva**: 2025. október 8.  
**Szerző**: Automatizálási Kísérlet  
**Verzió**: 1.0.0