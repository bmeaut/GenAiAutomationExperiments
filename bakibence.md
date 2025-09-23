**Nagy nyelvi modellek valós szoftverhiba-javítási képességeinek kvantitatív és kvalitatív elemzése**

Célkitűzés:

- LLM-ek elterjedtek a közelmúltban, sokan használják kódgenerálásra és programozásra
- algoritmikus kihívás megoldása vs. szoftvermérnök árnyalt, kontextusfüggő feladatai
- szakadék felmérése a kettő között egy kritikus kutatási kérdéssel:
- Hogyan viszonyulnak a modern LLM-ek hibajavító képességei az emberi fejlesztőkéhez valós, aktívan karbantartott, nyílt forráskódú szoftverprojektek esetében?

Jelenlegi Python tool, aminek a készítése folyamatban, az alábbi főbb elvek alapján gyűjtene ehhez adatot:

- GitHub API segítségével előre összeszedett, Python repo-kban commit-ok elérése, szűrése, issue-k gyűjtése
- kontextus kinyerés absztrakt szintaxisfával (AST)
    **Kristóf:** ez pontosabban mit takar? A Python kódból AST-t készítessz? És utána pontosan mi lesz vele?
- minden hiba esetén elszigetelt tesztkörnyezet létrehozása a hibajavítás előtti commit alapján
- template alapján készített prompt kontextussal választott LLM-nek, mely válasza egy diff patch
    **Kristóf:** a diff kimenet kikötését majd érdemes lesz megvizsgálni, hogy pl. egy LLM tud-e ugyanolyan hatékony lenni diff kimenettel, mint pl. ha ő szerkeszti a forráskódot agent módban.
- patch után a repo saját test suite-jának futtatása, teszteredmény hasonlítása a valós fix commit-hoz
- metrikák gyűjtése: pl. ciklomatikus és kognitív komplexitás

Jelenleg a toolt már kipróbáltam 3-4 kisebb, de népszerű Python repo-n, melyek test suite-ja aránylag gyorsan lefut, hogy gyorsabban tudjam javítani a rendszer hibáit.

Persze még rengeteg fejleszteni való van hátra (amennyiben belefér az időbe):

- kevesebb token használata
- tesztek készítése/generálása
- közvetlen API integráció: egyelőre kis számú tesztelt commit miatt még megengedhettem, hogy kézzel másoljam a promptokat a tool és a választott LLM között, hogy ne szaladjak bele hatalmas API költségekbe, amíg még gyakoriak a hibák
- több LLM modell teljesítményének összehasonlítása
- haladó elemzés: mutation testing minden verzióra
- automatizált report: results.csv alapján automatikus diagram és összefoglaló statisztika

Kiemelném, hogy a cél szerintem nem egy ilyen elemző framework készítése, hanem csak egy eszköz az eredmények megszerzéséhez.
