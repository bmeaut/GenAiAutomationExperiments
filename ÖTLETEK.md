# Saját infrastruktúra

Hosszabb távon az alkotásainkat érdemes lenne a weben, letölthető és szépen prezentált formában (leírás, screenshot stb.) közkinccsé tenni. Ennek egyik legegyszerűbb módja, ha ebben a repositoryban van egy GitHub Pages oldal is. Ekkor pl. egy docs könyvtár tartalmából a master branchen minden változáskor készül egy statikus HTML oldal, ami elérhető a bmeaut.github.io/GenAiAutomationExperiments oldalon. Ekkor a többi forráskóddal együtt bárki szerkesztheti az oldalt, könnyen tud készíteni egy új aloldalt az éppen elkészült projektje számára.

A GitHub Pages tipikusan a Jekyll rendszert használja ahhoz, hogy a stílus leírókat és a site keretét, valamint a tartalmat adó markdown fájlokat weboldallá konvertálja. Lehet lokálisan is futtatni debug célokra, egyébként meg szépen dolgozik a háttérben minden alkalommal, amikor egy commit hatására változik az oldal tartalma.

Feladat: kiválasztani az alap témát, customizálni, ahol kell, majd beüzemelni egy minta projekt leírással. [https://docs.github.com/en/pages/quickstart](https://docs.github.com/en/pages/quickstart)

# Ötletek a VIK Dékáni Hivatal támogatására

A Dékáni Hivatal munkatársai szeretettel várják a néhány érdeklődőt a feladatok részletes megbeszélésére.

## Excel Neptun kód anonimizáló (KÉSZ)

Tetszőleges Excel táblában, ami egy oszlopban Neptun-kódot tartalmaz, az adatok anonimizálása. Azért, hogy mi kaphassunk teszt adatokat. Ehhez minden Neptun-kódot egy sózott hash kódra kell lecserélni, ahol a só értékét az Excel makró egy felugró ablakban kéri be. Miven nem nagyon kritikus a garantált ütközésmentesség, elég lesz az sha1(só + NeptunKód) első 6 karaktere. Több munkalap között az anonimizált kódok komparibilitását úgy lehet biztosítani, ha ugyanazt a só értéket használjuk mindegyik anonimizálásakor.

## Jubileumi diplomák

Aki jubileumi diplomát szeretne, mindenki kitölt egy webes űrlapot, ami azonban nem támogatja a fájl csatolást, azt emailben küldik el (pl. önéletrajz), ezeket össze kell párosítani a kitöltési adatokkal. Ezután pl. a csatolt oklevél fényképen akár a sorozatszámot is lehetne ellenőrizni, hogy azt adta-e meg az űrlapon is. És lehet küldeni automatikus választ is, hogy érezze az illető a törődést. Az űrlap adatai mellé az Excel táblába akár egy cellába a teljes önéletrajzot is be lehet másolni, ha igény lesz rá.

## Akkreditációs megfeleltetés ellenőrzése

Ha egy hallgató pl. újrafelvételivel tantárgyakat akar akkreditálni, akkor kitölt egy Excel táblát, hogy melyik tárgyat melyiknek akarja elfogadtatni. Ezeket ellenőrizni kell, hogy az egyes tantervek közötti megfeleltetési szabályoknak eleget tesznek-e.

Az egymás utáni tantervekhez van megfeleltetési táblázat, de lehet, hogy "több tanterv ugrásnyit" kell haladni. A művelet elején kérdezze meg a makró, hogy mi a céltanterv. (Néha ugyanis a hallgató jobban jár, ha nem a legfrissebb tantervre ugrik át pl. újrafelvételinél, hanem egy korábbira, mert ott több tárgyat tud elfogadtatni és azzal a tantervvel is tud végezni.)

Mintafájlok Teams alatt.

## BProf portál - tömeges email írása

A BProf képzés kooperatív portáljával kapcsolatban (https://kooperativ.vik.bme.hu/) előfordul, hogy egy csomó cégnek kell emailt írni. Az email szövegében pár helyen be kell helyettesíteni pl. cég nevet vagy céges adatokat az XLSX alapján. Ezen kívül a táblázatban van egy oszlop, ami meghatározza a csatolandó fájl nevét (cégenként lehet, hogy mást kell csatolni, pl. ha egy rendezvényen részt vett, akkor azzal kapcsolatos anyagot is kap még.) Legyen lehetőség ;-vel elválasztva több fájlnév megadására is, hátha kelleni fog. Ezen kívül a felhasználó választhassa ki, hogy melyik e-mail címéről menjenek ki a generált levelek.

A cél, hogy a felhasználónak feldobjuk a kész leveleket az Outlook email szerkesztőjében, küldésre készen.

## BProf portál cégadat frissítés kérés emailben

A BProf portálon néha nem frissek a cégadatok. Ezért a Hivatal emailben megkérdezi, hogy van-e változás. A visszajövő emailekben megadott adatokat (az email törzsében lesz egy előre ismert formátumú táblázat) össze kell vetni a portálról kiexportált (xlsx) cégadatokkal és jelezni az eltéréseket az adminisztrátornak. Ezt egy Outlook makróval el lehet végezni, ami emaileket keres (a szövegtörzset könnyű felismerni, mert ismert sablon alapján megy ki), és kezeli az Excel táblát.

A cégek neve, adószáma néha megváltozhat, a táblázatban az első oszlopban lévő ID az, ami használható azonosításra.

Mintafájlok Teams alatt.

## Hallgatói előrehaladás kimutatás

Hallgatói előrehaladás adatok elemzése Excel alatt (minden félévben elég sok munka)

A kiindulási alap egy Excel tábla minden hallgató minden eredményével (külön sorban minden aláírás megadva/megtagadva, minden vizsgajegy). Hallgatónként és tárgyanként egyetlen sorba kell, hogy van-e aláírás és ha igen, mi az utolsó érvényes vizsgajegy.
Ilyen táblázat mindig csak néhány kiválasztott tantárgyra kell, pl. 1. féléves mintatantervi kötelező tárgyak.

Mintafájlok Teams alatt.

# Vegyes ötletek, bárki válaszhatja

- Sablon alapján dokumentum készítés excel táblából. A cél az, hogy egy excel táblában lévő adatok alapján bármelyik sorra le lehessen generálni egy dokumentumot, amiben a placeholderek helyén az excel táblában szereplő szövegek kerülnek be. Azért, hogy a megoldás (Excel makró) többet tudjon, mint a körlevél funkció, a táblázat egy részében számszerű adatok legyenek, amikből a makró készít egy diagrammot és azt is beszúrja a dokumentum megfelelő helyére, majd elmenti PDF-ben úgy, hogy a dokumentum nevét is a táblázat alapján határozza meg.

- Lásd TodoCalendarEntries könyvtár

- A félév időbeosztása naptár bejegyzések formájában: a cél egy olyan prompt, ami a kari honlapról (félév időbeosztása és a kari kiegészítés) kiszedi a szükséges adatokat és naptár bejegyzések formájában egy ical fájlba kiírja őket: minden szünetet, munkanap áthelyezést, valamint a szorgalmi időszak minden hetének hétfőjére berak egy egész napos bejegyzést, melybe beleírja, hogy hanyadik hét van.

- Teams alá hogyan lehetne olyan botot készíteni, ami minden héten mindenkit megpingel szerda este, aki még nem küldött workoutloud postot a bot által figyelt csatornába? (A bot lehet például egy Teams-től függetlenül, ütemezetten lefuttatott Python script is.)

- Sablon alapján sok emailt előkészítő script/makró: egy placeholdereket tartalmazó email sablon és egy beszúrandó szövegeket és email címeket tartalmazó táblázat alapján a makró a táblázat minden sorához feldob egy email ablakot kitöltve, hogy már csak a "Küldés"-re kelljen rákattintani. Példa felhasználás: minden hallgatónak névre szóló e-mail arról, hogy ne felejtse el kitölteni a záróvizsga adatlapot. Továbbfejlesztés: a táblázat egyik mezője azt határozza meg, hogy több lehetséges sablon közül melyiket használja a makró. Pl. szakdolgozat és diplomaterv esetében kicsit eltérnek a teendők. És a sablon kiválasztó mező lehet üres is, akkor arra a sorra nem készül email.

- Emailben kérdező és válaszokat összegyűjtő megoldás: Excel makró, mely egy táblázat alapján kiküld e-maileket (táblázatban adott email cím, név a megszólításhoz, esetleg sablon kiválasztó oszlop, valamint az email sablon placeholdereibe illesztendő szöveg), majd egy másik makró végignézi a bejövő emaileket és ha jött válasz (a címzettől és subject alapján az a válasz), akkor LLM segítségével kinyeri a kérdésre adott választ és beírja az Excel táblába. Pl. névre szóló emailben mindenkitől megkérdezzük, hogy milyen címet adna a szakdolgozatának. LLM helyett első körben lehet olyan emailt is írni, amiben egyértelmű a válasz helye és akkor onnan kiparsolja a válaszgyűjtő makró/script.

- Lapozgatós naptár generáló program: minden hónaphoz adott egy kép, ami a naptáron a napok táblázata felett látható. A sablon könnyű szerkeszthetősége érdekében lehet akár Excel fájl is, de például SVG fájl is (vektoros, XML alapú képformátum). Továbbfejlesztésként egy táblázatból kiveheti a piros betűs ünnepeket is, melyekhez akár szöveges megjegyzés is tartozhat (pl. családi születésnapok).

- Interakció Google Sheets, Goodle Docs, Excel és Word, office makrók között. Ez egy technológiai kísérleti feladat, mely arra keresi a választ, hogy hogyan lehet pl. Excel makróból vagy egy Python scriptből könnyen elérni a fenti adatforrásokat, azon között adatokat átvinni. Pl. Google Forms kimenetét tartalmazó Google Sheet táblázat minden új sorához egy Word sablon alapján PDF dokumentum generálása, majd csatolása egy a táblázat alapján megcímzett emailhez, elküldésre készen feldobva a felhasználónak.

