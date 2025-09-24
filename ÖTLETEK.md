# Vegyes ötletek, bárki válaszhatja

- Sablon alapján dokumentum készítés excel táblából. A cél az, hogy egy excel táblában lévő adatok alapján bármelyik sorra le lehessen generálni egy dokumentumot, amiben a placeholderek helyén az excel táblában szereplő szövegek kerülnek be. Azért, hogy a megoldás (Excel makró) többet tudjon, mint a körlevél funkció, a táblázat egy részében számszerű adatok legyenek, amikből a makró készít egy diagrammot és azt is beszúrja a dokumentum megfelelő helyére, majd elmenti PDF-ben úgy, hogy a dokumentum nevét is a táblázat alapján határozza meg.

- Lásd TodoCalendarEntries könyvtár

- A félév időbeosztása naptár bejegyzések formájában: a cél egy olyan prompt, ami a kari honlapról (félév időbeosztása és a kari kiegészítés) kiszedi a szükséges adatokat és naptár bejegyzések formájában egy ical fájlba kiírja őket: minden szünetet, munkanap áthelyezést, valamint a szorgalmi időszak minden hetének hétfőjére berak egy egész napos bejegyzést, melybe beleírja, hogy hanyadik hét van.

- Teams alá hogyan lehetne olyan botot készíteni, ami minden héten mindenkit megpingel szerda este, aki még nem küldött workoutloud postot a bot által figyelt csatornába? (A bot lehet például egy Teams-től függetlenül, ütemezetten lefuttatott Python script is.)

- Sablon alapján sok emailt előkészítő script/makró: egy placeholdereket tartalmazó email sablon és egy beszúrandó szövegeket és email címeket tartalmazó táblázat alapján a makró a táblázat minden sorához feldob egy email ablakot kitöltve, hogy már csak a "Küldés"-re kelljen rákattintani. Példa felhasználás: minden hallgatónak névre szóló e-mail arról, hogy ne felejtse el kitölteni a záróvizsga adatlapot. Továbbfejlesztés: a táblázat egyik mezője azt határozza meg, hogy több lehetséges sablon közül melyiket használja a makró. Pl. szakdolgozat és diplomaterv esetében kicsit eltérnek a teendők. És a sablon kiválasztó mező lehet üres is, akkor arra a sorra nem készül email.

- Emailben kérdező és válaszokat összegyűjtő megoldás: Excel makró, mely egy táblázat alapján kiküld e-maileket (táblázatban adott email cím, név a megszólításhoz, esetleg sablon kiválasztó oszlop, valamint az email sablon placeholdereibe illesztendő szöveg), majd egy másik makró végignézi a bejövő emaileket és ha jött válasz (a címzettől és subject alapján az a válasz), akkor LLM segítségével kinyeri a kérdésre adott választ és beírja az Excel táblába. Pl. névre szóló emailben mindenkitől megkérdezzük, hogy milyen címet adna a szakdolgozatának. LLM helyett első körben lehet olyan emailt is írni, amiben egyértelmű a válasz helye és akkor onnan kiparsolja a válaszgyűjtő makró/script.

- Lapozgatós naptár generáló program: minden hónaphoz adott egy kép, ami a naptáron a napok táblázata felett látható. A sablon könnyű szerkeszthetősége érdekében lehet akár Excel fájl is, de például SVG fájl is (vektoros, XML alapú képformátum). Továbbfejlesztésként egy táblázatból kiveheti a piros betűs ünnepeket is, melyekhez akár szöveges megjegyzés is tartozhat (pl. családi születésnapok).

- Interakció Google Sheets, Goodle Docs, Excel és Word, office makrók között. Ez egy technológiai kísérleti feladat, mely arra keresi a választ, hogy hogyan lehet pl. Excel makróból vagy egy Python scriptből könnyen elérni a fenti adatforrásokat, azon között adatokat átvinni. Pl. Google Forms kimenetét tartalmazó Google Sheet táblázat minden új sorához egy Word sablon alapján PDF dokumentum generálása, majd csatolása egy a táblázat alapján megcímzett emailhez, elküldésre készen feldobva a felhasználónak.

