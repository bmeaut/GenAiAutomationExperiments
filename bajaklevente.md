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
