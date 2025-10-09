# Adminisztratív fájdalomcsillapító - MI alapú munka automatizálás

**Hallgató**: Baják Levente Imre

**Konzulens**: Dr. Csorba Kristóf

**Tárgy**: Önálló laboratórium 2 (BMEVIAUML11)

Az előző önlabon Selenium alapú automatizálással foglalkoztam, Python nyelven.

Ebben a félévben a Dékáni Hivatallal közösen keresett adminisztrációs feladatok automatizálásával fogok foglalkozni,
első sorban _vibe coding_ módszerrel, melynek a folyamatát és eredményét dokumentálom.

# Work out loud

## 2. hét

Bemutatkozás, feladatkeresés, ötletelés.

### Következő feladatok

- Saját projekt kitalálása / keresése (később: adminisztrációs feladatok automatizálása)
- GitHub branch létrehozása, eredmények feltöltése
    - Projektenként egy mappa, benne README.md

## 3. hét

### Pizza rendelő bot készítése

A projekt során egy konzolból vezérelhető botot készítettem el, mely capripizzeria.hu oldalról történő pizza rendelést
automatizálja. A fejlesztéshez a _vibe coding_ módszert alkalmaztam, a [Kiro](https://kiro.dev/) nevű (várólistás)
fejlesztőkörnyezetet használva. Bár a Kiro számos funkcióval rendelkezik a specifikáció alapú kódolás elősegítésére, én
csak a Claude Sonnet 4 modellt használó ágenst vettem igénybe.

A master promptot pontosan és részletesen írtam meg - talán túlságosan is. Leírtam a program elvárt működését, valamint
konkrétan megneveztem benne a szükséges HTML elemek azonosítóit, ahelyett, hogy a weboldal teljes forráskódját átadtam
volna. Ez viszonylag egyértelművé tette a feladatot az agent számára.

A teljes beszélgetés a `Pizza/CHAT.md` fájlban található. (bajaklevente branch)

#### Eredmények

A bot képes a támogatott irányítószámok ellenőrzésére, a pizzák (fuzzy) keresésére, méret- és mennyiségválasztásra,
valamint a rendelési adatok automatikus kitöltésére.

A részletes leírás és a használati útmutató a `Pizza/README.md` fájlban található. (bajaklevente branch)

## 4. hét

### Redmine munkaidő-nyilvántartás automatizálása

A projekt során egy teljes automatizált workflow-t készítettem Redmine alapú munkaidő-nyilvántartás Excel táblázattá alakításához. A fejlesztéshez GitHub Copilot Chat-et használtam, mely három Python modult hozott létre: Selenium alapú CSV exportot, CSV feldolgozót és a kettőt összekötő főprogramot.

A master prompt részletesen leírta a webes automatizálás lépéseit, beleértve a konkrét HTML elemek azonosítóit. Különösen hasznos funkció a verbose/quiet mód implementálása, mely fejlesztéskor részletes debug információkat jelenít meg, éles használatban viszont csak a lényeges kimenetet.

A teljes beszélgetés a `WorkHours/CHAT.md` fájlban található.

#### Eredmények

A script képes a Redmine-ba való automatikus bejelentkezésre, dátum- és felhasználói szűrők beállítására, CSV export automatizálására, valamint Excel táblázat generálására a cég sablonján alapulva. Kezeli a magyar karaktereket (ANSI encoding), hétvégéket és többszörös bejegyzéseket.

A részletes leírás és a használati útmutató a `WorkHours/README.md` fájlban található.

## 5. hét

### Neptun kód anonimizáló Excel makró

A projekt során egy Excel VBA makrót készítettem, amely Neptun-kódokat anonimizál teszt adatok létrehozásához. A megoldás sózott SHA-1 hash-t használ: minden kódot a `SHA-1(só + NeptunKód)` első 6 karakterére cserél. A GitHub Copilot Chat fokozatosan építette fel a megoldást, két használati móddal: interaktív tartomány kijelöléssel és teljes oszlop feldolgozással.

Egy érdekes probléma merült fel: az Excel automatikusan tudományos jelölésre (5.27E+12) alakította a hexadecimális eredményeket. A megoldás az explicit szöveg formátum beállítása volt a cellákra (`cell.NumberFormat = "@"`).

A teljes beszélgetés a `NeptunAnonymizer/CHAT.md` fájlban található.

#### Eredmények

A makró képes konzisztens anonimizálásra (azonos só + kód = azonos eredmény), támogatja a többszörös munkalapokat, kezeli a duplikált kódokat és magyar karaktereket. Példa kimenet "test123" sóval: ABC123 → E02E6B, XYZ789 → 130F2A.

A részletes leírás és a használati útmutató a `NeptunAnonymizer/README.md` fájlban található.
