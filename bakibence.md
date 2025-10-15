**Nagy nyelvi modellek valós szoftverhiba-javítási képességeinek kvantitatív és kvalitatív elemzése**

Célkitűzés:

- LLM-ek elterjedtek a közelmúltban, sokan használják kódgenerálásra és programozásra
- algoritmikus kihívás megoldása vs. szoftvermérnök árnyalt, kontextusfüggő feladatai
- szakadék felmérése a kettő között egy kritikus kutatási kérdéssel:
- Hogyan viszonyulnak a modern LLM-ek hibajavító képességei az emberi fejlesztőkéhez valós, aktívan karbantartott, nyílt forráskódú szoftverprojektek esetében?

Jelenlegi Python tool, aminek a készítése folyamatban, az alábbi főbb elvek alapján gyűjtene ehhez adatot:

- GitHub API segítségével előre összeszedett, Python repo-kban commit-ok elérése, szűrése, issue-k gyűjtése
- kontextus kinyerés absztrakt szintaxisfával (AST)
   - **Kristóf:** ez pontosabban mit takar? A Python kódból AST-t készítessz? És utána pontosan mi lesz vele?
- minden hiba esetén elszigetelt tesztkörnyezet létrehozása a hibajavítás előtti commit alapján
- template alapján készített prompt kontextussal választott LLM-nek, mely válasza egy diff patch
   - **Kristóf:** a diff kimenet kikötését majd érdemes lesz megvizsgálni, hogy pl. egy LLM tud-e ugyanolyan hatékony lenni diff kimenettel, mint pl. ha ő szerkeszti a forráskódot agent módban.
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

# 3. heti "Work Out Loud"
## Mivel foglalkoztam eddig
Python tool készítése, ami:
- népszerű, sokat tesztelt Python git repók commitjain végighalad, szűri a javításokat, majd elmenti a javítás előtti és utána lévő verziókat
- keres említett issue (bug) jelentéseket
- létrehoz egy szeparált Python környezetet, ahol minden fejlesztéshez szüksékes függőséget próbál telepíteni
- kódmetrikákat mér
- javítás utáni verzióra lefuttatja a saját tesztjeit
- javítás előtti verzióra készít egy promptot, amire kapott LLM válasz (egyelőre kézzel) egy diff-et tartalmaz, ami javítani próbálja a bugot, majd erre is lefuttatja a teszteket
- amit csak lehet információt elment .csv, .log fájlokba

## Mivel fogok foglalkozni jövő héten
- javítani a projektekhez tartozó saját tesztkörnyezetek telepítését, még sok a hiba
- LLM API használatnak utánanézni
- promptba kerülő kontextus szűkítése, hogy kevesebb tokenbe kerüljön 1-1 javítási próbálkozás
- mutation testing is kerüljön a saját test suite mellé?

# 4. heti "Work Out Loud"
## Mivel foglalkoztam eddig
Python tool fejlesztése és javítása
- A pipeline már projektenként csak egyszer telepít függőségeket, ami gyorsítja az elemzést, commitonkénti újraépítés overkill elővigyázatosság volt.
- Flaky tesztek kezelése: a megbízhatatlan tesztek, tesztfájlok kizárhatóak a vizsgálatból.
    - Függőségek verzióváltozása visszamenőleges tesztek hibátlan lefutását akadályozza, ha nem volt trackelve, hogy a teszt és commit idején milyen volt a ponton függőség-verzió, illetve WSL virtuális gépből is adódhatnak hibák
    - Bizonyítékokat még keresem
- A rendszer már képes kezelni több fájlt érintő javításokat is.
- QoL: munkafolyamat megkönnyítése
    - Pause/Stop/Resume funkció: A mondjuk egy analysis run áll 10 repoból és repónként 50 commitból, akkor a környezetek építése és a tesztek lefutása sok idő, le lehessen állítani, köztes adat ne vesszen el.
    - A begyűjtött commit-ok kilistázódnak a GUI-ban, egy-egy specifikusat is lehet futtatni már, nem kell hozzá módosítani a config fájlban az elemzett repókat.
    - Színes, átlátható logok: Jobban látszik, hogyan haladnak az adott projekt vagy commit tesztjei, könnyebb észlelni a hibákat.
    - Bővítettem a `results.csv`-be mentett adatokat

## Mivel fogok foglalkozni jövő héten

Kerestem kapcsolódó forrásokat, melyeket fel szeretnék dolgozni, mielőtt javítom a fájlokból való kontextus kinyerést, illetve elkezdem az API vagy Agent használatot a programon belül.
- *[A Survey of LLM-based Automated Program Repair: Taxonomies, Design Paradigms, and Applications](https://arxiv.org/html/2506.23749v1)*
- *[An Empirical Study on LLM-based Agents for Automated Bug Fixing](https://arxiv.org/html/2411.10213v1)*
- *[Bug Fixing with Broader Context: Enhancing LLM-Based Program Repair via Layered Knowledge Injection](https://arxiv.org/html/2506.24015v1)*
- *[Large Language Models Meet Automated Program Repair: Innovations, Challenges and Solutions](https://www.researchgate.net/publication/387253731_Large_Language_Models_Meet_Automated_Program_Repair_Innovations_Challenges_and_Solutions/fulltext/6765655b894c5520851f2f95/Large-Language-Models-Meet-Automated-Program-Repair-Innovations-Challenges-and-Solutions.pdf)*
- *[On the Role of Context Granularity in LLM-Driven Program Repair](https://mlforsystems.org/assets/papers/neurips2024/paper23.pdf)*

# 6. heti "Work Out Loud"
## Mivel foglalkoztam eddig: egész jól utolértem magam
Tovább fejlesztettem a Python toolt, amivel LLM-ek szoftverhiba javítási képességeit vizsgálom.
- Refaktoráltam a legtöbb modult, néhány rész még hátra van
	- Bölcsebb lett volna a publikáció olvasás, design, programozás sorrendben haladni, nem fordítva.
- Pár új funkció:
    - API integráció: GUI-ból választható modell (Gemini 2.5 Pro/Flash/Flash-Lite, mert ez ingyenes Google AI Studioban)
        - Új elmentett adat: LLM modell, válasz idő, token használat
    - Ha egy PR-ban vagy issueban hivatkoznak egy másik issuera, azt is begyűjti a tool
    - Javított kontextus kinyerés: átgondoltan választott kódrészlet, hívási struktúra, git history, stb.
    - Választ eddig ```diff``` formátumban vártam, semmilyen prompttal nem sikerült konzisztensen szintaktikailag helyes diffet kapni, egy inkább JSON-t kérek és abból generálom a diffet, ez sokkal megbízhatóbb eddig.
    - Ha már `pytest`-et használok minden tesztelt repóhoz, ideje volt nekem is elkezdeni tesztelni a kódot, ahogyan nőtt a mérete. Azért is volt szükség refaktorálásra, hogy könnyebben lehessen tesztelni.

Projekt végén az begyűjtött adatokat elemezni kell: **Jupyter notebook**kal ismerkedtem, hogy `pandas` és `matplotlib` segítségével **szép formában tudjak majd kimutatásokat készíteni** Pythonban. Futtatható Python kód snippeteket és szöveget tartalmaz, célszerűnek tartom hogy a végső adathalmaz elemzését ellenőrizni lehessen:
- Beüzemeltem ezért egy kezdetleges **GitHub Pages oldal**t: https://engemkeres.github.io/llm-analysis-thesis/
- Az `analysis.ipynb` fájlból **GitHub Action** segítségével **Quarto**t használva egy statikus HTML-t generálok.
- Mivel statikus az oldal, de egyszerű ellenőrizhetőséget akartam, így hozzáadtam egy **Google Colabs** gombot az oldalhoz, ami segítségével bárki bármilyen telepítés nélkül tudja futtatni az `analysis.ipynb` tartalmát, automatikusan elérhető Colabban a `results.csv` is, ami az oldal repójában található.
- Készítettem egy **bash script**et, ami:
    - Átmásolja az `analysis.ipynb` és a `results.csv` fájlokat a GitHub Pages oldalhoz tartozó lokális repóba.
    - Automatikus commit+push, ami elindítja a GitHub Actions deployt, hogy a Jupyter fájlból a `Quarto` statikus weboldalt generáljon. (Azért van másik repoban a GitHub Pages oldal, mert nem akartam elsőre valamit elrontani a közös repóban)

Illetve feldolgoztam az összegyűjtött publikációkat.

## Mivel fogok foglalkozni jövő héten
- Refaktorálás folytatása
- Jobban belebújtam a publikációkba, így van pár ötlet, hogy milyen irányba lehetne javítani a kontextus kinyerést
- `mini-SWE-agent` integráció, hogy a diff generálás helyett a modell maga szerkessze a fájlokat?
- `pytest` tesztek írása
- Analízis gyorsítási tervek, ha minden más jól működik:
    - párhuzamosítás: több repó, commit egyszerre, ha bírja a gépem
    - batch LLM API hívások
    - incremental environment setup: amíg összeszedem a bug kontextust, elég a leklónozott repo, nem kell a test setupnak elérhetőnek lennie, az készülhet addig, amíg az LLM válaszra várok
    - csak releváns tesztek futtatása, nem az összes
    - `pytest` optimalizálás