# Hallgatói előrehaladás kimutatás

Hallgatói előrehaladás adatok elemzése és összesítése Excel formátumban.

## Probléma

Minden félévben jelentős manuális munkát igényel a hallgatói előrehaladási adatok feldolgozása. A kiindulási pont egy Excel tábla, amely minden hallgató minden eredményét tartalmazza - külön sorban minden aláírás megadva/megtagadva bejegyzés és minden vizsgajegy. Ezt az adathalmazt át kell alakítani egy áttekinthetőbb formátumba, ahol hallgatónként és tárgyanként egyetlen sorban látható, hogy van-e aláírás, és ha igen, mi az utolsó érvényes vizsgajegy.

## Megoldás

Ez az alkalmazás automatizálja a fenti folyamatot. Egyszerűen hozzáadod a feldolgozandó tantárgyakat (pl. 1. féléves mintatantervi kötelező tárgyak), és az alkalmazás létrehoz egy áttekinthető Excel táblázatot a kiválasztott tárgyakra.

## Telepítés

### Követelmények

- Python 3.8 vagy újabb

### Telepítési lépések

1. Klónozd le vagy töltsd le a projektet
2. Nyiss egy terminált a projekt mappájában
3. Telepítsd a szükséges csomagokat:

```bash
pip install -r requirements.txt
```

## Használat

### Alkalmazás indítása

```bash
python hallgatoi_elorehaladas.py
```

### Funkciók

#### 1. Kurzusok kezelése

**Kurzus hozzáadása:**
- Add meg a tárgykódot
- Válaszd ki a bejegyzés típusát:
  - **Évközi jegy**: Egyoszlopos kurzus, évközi érdemjegy
  - **Aláírás + Vizsgajegy**: Kétoszlopos kurzus, aláírás és vizsgajegy
  - **Aláírás**: Egyoszlopos kurzus, csak aláírás
  - **Szigorlat**: Egyoszlopos kurzus, szigorlat jegy
- Kattints a "Hozzáadás" gombra vagy nyomj Entert

**Kurzus törlése:**
- Válaszd ki a kurzust a listában
- Kattints a "Kijelölt törlése" gombra

#### 2. Kurzuslista mentése és betöltése

**Kurzusok exportálása:**
- Kattints a "Kurzusok exportálása" gombra
- A kurzuslista JSON formátumban kerül mentésre

**Kurzusok importálása:**
- Kattints a "Kurzusok importálása" gombra
- Válaszd ki a korábban mentett JSON fájlt
- A meglévő kurzusok felülíródnak

#### 3. Excel fájl generálása

**Lépések:**

1. **Hallgatói adatok betöltése:**
   - Kattints a "Tallózás..." gombra
   - Válaszd ki a hallgatói adatokat tartalmazó Excel fájlt
   - A fájlnak tartalmaznia kell a következő oszlopokat:
     - Modulkód
     - Felvétel féléve
     - Neptun kód
     - Nyomtatási név
     - Tárgykód
     - Tárgynév
     - Bejegyzés értéke
     - Bejegyzés típusa
     - Bejegyzés dátuma
     - Érvényes

2. **Excel fájl létrehozása:**
   - Kattints az "Excel fájl létrehozása" gombra
   - Add meg a mentési helyet és fájlnevet
   - Az alkalmazás automatikusan feldolgozza az adatokat

**Kimeneti fájl szerkezete:**

Az Excel fájl az alábbi oszlopokat tartalmazza:
- **Alapadatok** (minden hallgatónál):
  - Modulkód
  - Felvétel féléve
  - Neptun kód
  - Nyomtatási név
  - Felvételi összes pontszám (üres)
  - Státusz (üres)

- **Kurzus oszlopok** (a hozzáadott kurzusok sorrendjében):
  - Évközi jegy / Szigorlat / Aláírás: 1 oszlop
  - Aláírás + Vizsgajegy: 2 oszlop (aláírás | vizsgajegy)

**Adatfeldolgozás logikája:**

- **Évközi jegy / Szigorlat:**
  - A legfrissebb érvényes bejegyzés kerül be

- **Aláírás:**
  - A legfrissebb aláírás bejegyzés kerül be

- **Aláírás + Vizsgajegy:**
  - Bal oszlop: Legfrissebb aláírás (Aláírva/Megtagadva)
  - Jobb oszlop: Ha aláírás = "Aláírva", akkor a legfrissebb érvényes vizsgajegy
  - Ha aláírás = "Megtagadva", a jobb oszlop üres marad

## Naplózás

Az alkalmazás automatikusan naplóz minden műveletet az Excel generálás során:

- **Ha nincsenek hibák/figyelmeztetések:** A naplófájl automatikusan törlődik
- **Ha vannak hibák/figyelmeztetések:** A naplófájl megmarad és a név a kimeneti fájl neve + `_log_ÉÉÉÉHHNN_ÓÓPPMM.txt`

A naplófájl tartalmazza:
- Feldolgozott adatok mennyisége
- Minden egyes kurzus feldolgozásának részletei
- Hiányzó vagy érvénytelen adatok figyelmeztetései
- Hibák részletes leírása

## Fájlformátumok

### Kurzuslista JSON formátum

```json
[
  {
    "course_code": "BMEVISZAA00",
    "grading_type": "Évközi jegy"
  },
  {
    "course_code": "BMEVISZAB00",
    "grading_type": "Aláírás + Vizsgajegy"
  }
]
```

## Hibaelhárítás

### "Érvénytelen fájl" hiba
- Ellenőrizd, hogy a hallgatói Excel fájl tartalmazza az összes szükséges oszlopot
- Az oszlopneveknek pontosan egyezniük kell a fent felsoroltakkal

### Üres cellák a kimeneti fájlban
- Ellenőrizd a naplófájlt, ha létrejött
- Lehet, hogy az adott hallgatónak nincs érvényes bejegyzése az adott kurzushoz
- Ellenőrizd, hogy a tárgykód pontosan egyezik a forrás fájlban és a kurzuslistában

### Az alkalmazás nem indul
- Ellenőrizd, hogy telepítve vannak-e a szükséges csomagok: `pip install -r requirements.txt`
- Ellenőrizd a Python verziót: `python --version` (minimum 3.8 szükséges)

## Technikai részletek

- **Programozási nyelv:** Python 3
- **GUI keretrendszer:** tkinter
- **Fő könyvtárak:**
  - pandas: Adatfeldolgozás
  - openpyxl: Excel fájl írás/olvasás
  - logging: Naplózás

## Licensz

Ez a projekt oktatási célra készült.
